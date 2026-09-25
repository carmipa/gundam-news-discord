"""
Saúde do contêiner: healthcheck que enxerga o bot, e arranque que recusa rodar
sem conseguir gravar o próprio estado.

Achados da auditoria de 2026-09-25:
  - o HEALTHCHECK só conferia se /app/config.json existia: `healthy` com o bot
    desconectado ou travado (e até com um DIRETÓRIO no lugar do arquivo);
  - com o contêiner passando a rodar sem root, arquivos montados do host com
    dono root deixariam o bot publicar sem nunca gravar o dedup — repostando
    tudo a cada ciclo, porque `save_json_safe` só registra o erro.
"""
import ast
import os
import stat
import subprocess
import sys
import time

import pytest

from utils.heartbeat import batimento_recente, caminho_heartbeat, registrar_batimento
from utils.storage import verificar_gravacao

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def heartbeat(tmp_path, monkeypatch):
    arquivo = tmp_path / "hb"
    monkeypatch.setenv("HEARTBEAT_FILE", str(arquivo))
    return arquivo


class TestBatimento:
    def test_desconectado_nao_bate(self, heartbeat):
        assert registrar_batimento(False) is False
        assert batimento_recente() is False

    def test_conectado_bate(self, heartbeat):
        assert registrar_batimento(True) is True
        assert batimento_recente() is True

    def test_batimento_velho_reprova_e_o_limite_aprova(self, heartbeat):
        registrar_batimento(True, agora=1000.0)
        assert batimento_recente(idade_maxima=180, agora=1180.0) is True
        assert batimento_recente(idade_maxima=180, agora=1181.0) is False

    def test_script_de_healthcheck_devolve_o_codigo_certo(self, heartbeat):
        env = dict(os.environ, HEARTBEAT_FILE=str(heartbeat))
        cmd = [sys.executable, os.path.join(RAIZ, "healthcheck.py")]
        assert subprocess.run(cmd, env=env, cwd=RAIZ).returncode == 1
        registrar_batimento(True)
        assert subprocess.run(cmd, env=env, cwd=RAIZ).returncode == 0
        velho = time.time() - 600
        os.utime(caminho_heartbeat(), (velho, velho))
        assert subprocess.run(cmd, env=env, cwd=RAIZ).returncode == 1


class TestVerificarGravacao:
    def test_arquivo_gravavel_passa(self, tmp_path):
        f = tmp_path / "state.json"
        f.write_text("{}", encoding="utf-8")
        assert verificar_gravacao([str(f)]) == []

    def test_arquivo_ausente_em_pasta_gravavel_passa(self, tmp_path):
        assert verificar_gravacao([str(tmp_path / "data" / "ultimo-bom" / "state.json")]) == []

    def test_diretorio_no_lugar_do_arquivo_reprova(self, tmp_path):
        (tmp_path / "history.json").mkdir()
        (problema,) = verificar_gravacao([str(tmp_path / "history.json")])
        assert "DIRETÓRIO" in problema

    def test_arquivo_somente_leitura_reprova(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text("{}", encoding="utf-8")
        os.chmod(f, stat.S_IREAD)
        try:
            if os.access(f, os.W_OK):
                pytest.skip("o sistema de arquivos ignora o bit de escrita (root?)")
            (problema,) = verificar_gravacao([str(f)])
            assert "sem permissão" in problema
        finally:
            os.chmod(f, stat.S_IREAD | stat.S_IWRITE)


class TestMainLigaAsDuasGuardas:
    def _main(self):
        return ast.parse(open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read())

    def test_verificacao_de_gravacao_vem_antes_do_bot_start(self):
        fonte = open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read()
        assert fonte.index("verificar_gravacao(") < fonte.index("await bot.start(TOKEN)")
        assert "raise SystemExit(" in fonte

    def test_loop_de_batimento_e_iniciado_no_on_ready(self):
        on_ready = next(
            n for n in ast.walk(self._main())
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "on_ready"
        )
        chamadas = [
            c for c in ast.walk(on_ready)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == "start" and getattr(c.func.value, "id", "") == "batimento"
        ]
        assert chamadas

    def test_dockerfile_usa_o_healthcheck_de_batimento_e_usuario_sem_root(self):
        df = open(os.path.join(RAIZ, "Dockerfile"), encoding="utf-8").read()
        assert 'CMD ["python", "healthcheck.py"]' in df
        assert "config.json') else 1" not in df
        assert "\nUSER mafty\n" in df
