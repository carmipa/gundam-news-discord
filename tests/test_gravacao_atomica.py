"""
Gravação dos JSON de estado sem arquivo truncado, e recuperação quando truncar.

Achado da auditoria de 2026-09-25: `save_json_safe` fazia `open(path, "w")` e
depois `json.dump`. O "w" zera o arquivo antes de escrever; disco cheio ou
SIGKILL nesse intervalo deixava o config.json vazio, a leitura seguinte devolvia
{} e o bot ficava mudo em todas as guilds com um único aviso no log.

Cada teste tem o caso doente e o legítimo com o mesmo sinal (A1), e verifica o
arquivo RELIDO do disco (A6).
"""
import errno
import json
import os

import pytest

import utils.storage as storage
from utils.storage import caminho_ultimo_bom, load_json_safe, save_json_safe


def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def arquivo(tmp_path):
    caminho = tmp_path / "config.json"
    assert save_json_safe(str(caminho), {"111": {"channel_id": 1}}) is True
    return str(caminho)


class TestNuncaTruncaODestino:
    def test_dado_nao_serializavel_nao_toca_no_arquivo(self, arquivo):
        assert save_json_safe(arquivo, {"x": object()}) is False
        assert ler(arquivo) == {"111": {"channel_id": 1}}

    def test_legitimo_dado_serializavel_substitui(self, arquivo):
        assert save_json_safe(arquivo, {"222": {"channel_id": 2}}) is True
        assert ler(arquivo) == {"222": {"channel_id": 2}}

    def test_disco_cheio_na_escrita_mantem_o_conteudo_anterior(self, arquivo, monkeypatch):
        def sem_espaco(_fd):
            raise OSError(errno.ENOSPC, "No space left on device")

        monkeypatch.setattr(storage.os, "fsync", sem_espaco)
        assert save_json_safe(arquivo, {"222": {"channel_id": 2}}) is False
        monkeypatch.undo()
        assert ler(arquivo) == {"111": {"channel_id": 1}}

    def test_nao_deixa_temporarios_para_tras(self, arquivo, monkeypatch):
        pasta = os.path.dirname(arquivo)
        monkeypatch.setattr(storage.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError(errno.ENOSPC, "x")))
        save_json_safe(arquivo, {"a": 1})
        monkeypatch.undo()
        save_json_safe(arquivo, {"b": 2})
        sobras = [n for n in os.listdir(pasta) if n.endswith(".tmp")]
        assert sobras == []


class TestArquivoMontadoPeloDocker:
    def test_replace_recusado_grava_no_lugar_e_preserva_o_inode(self, arquivo, monkeypatch):
        """
        `./config.json:/app/config.json` monta o ARQUIVO: renomear por cima do
        ponto de montagem dá EBUSY. A gravação tem de continuar funcionando e
        manter o mesmo inode, senão o host deixa de ver o arquivo do container.
        """
        inode_antes = os.stat(arquivo).st_ino
        replace_real = os.replace

        def replace_busy(origem, destino):
            if os.path.abspath(destino) == os.path.abspath(arquivo):
                raise OSError(errno.EBUSY, "Device or resource busy")
            return replace_real(origem, destino)

        monkeypatch.setattr(storage.os, "replace", replace_busy)
        assert save_json_safe(arquivo, {"222": {"channel_id": 2}}) is True
        monkeypatch.undo()
        assert ler(arquivo) == {"222": {"channel_id": 2}}
        assert os.stat(arquivo).st_ino == inode_antes


class TestRecuperacaoDaUltimaCopiaBoa:
    def test_arquivo_vazio_e_recuperado(self, arquivo):
        open(arquivo, "w").close()
        assert load_json_safe(arquivo, {}) == {"111": {"channel_id": 1}}

    def test_json_cortado_no_meio_e_recuperado(self, arquivo):
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write('{"111": {"chan')
        assert load_json_safe(arquivo, {}) == {"111": {"channel_id": 1}}

    def test_legitimo_arquivo_integro_e_lido_como_esta(self, arquivo):
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump({"333": {}}, f)
        assert load_json_safe(arquivo, {}) == {"333": {}}

    def test_arquivo_ausente_nao_ressuscita_copia_antiga(self, arquivo):
        os.remove(arquivo)
        assert load_json_safe(arquivo, {"padrao": True}) == {"padrao": True}

    def test_sem_copia_cai_no_padrao(self, tmp_path):
        caminho = tmp_path / "state.json"
        caminho.write_text("", encoding="utf-8")
        assert load_json_safe(str(caminho), {"padrao": True}) == {"padrao": True}

    def test_copia_fica_ao_lado_do_arquivo_e_nao_no_diretorio_de_trabalho(self, arquivo, tmp_path):
        esperado = tmp_path / "data" / "ultimo-bom" / "config.json"
        assert caminho_ultimo_bom(arquivo) == str(esperado)
        assert ler(str(esperado)) == {"111": {"channel_id": 1}}
