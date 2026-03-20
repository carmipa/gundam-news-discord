# Solução de problemas (troubleshooting)

[Voltar ao índice da documentação](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)

---

<details>
<summary><b>CommandNotFound: Application command set_canal not found</b></summary>

**Causa:** Sincronizacao global lenta do Discord.

**Solucao:** O bot faz sync por guild no `on_ready()`. Aguarde alguns segundos apos o bot conectar.

</details>

<details>
<summary><b>Bot nao tem permissao para enviar mensagens</b></summary>

**Causa:** Bot sem permissoes no canal configurado.

**Solucao:** 
1. Verifique as permissoes do bot no servidor
2. Use `/set_canal` novamente
3. Conceda **Enviar Mensagens** e **Incorporar Links**

</details>

<details>
<summary><b>PyNaCl is not installed voice will NOT be supported</b></summary>

**Isso nao e erro.** Aviso apenas; o bot nao usa voz.

</details>

<details>
<summary><b>URL bloqueada por seguranca</b></summary>

**Causa:** IP privado ou dominio local (anti-SSRF).

**Solucao:** Confira se a URL em `sources.json` e publica e correta.

</details>

<details>
<summary><b>UnicodeEncodeError / emojis no console (Windows)</b></summary>

**Causa:** Terminal em encoding regional (ex.: cp1252).

**Solucao:** `utils/logger.py` usa UTF-8 no Windows quando possivel. Se precisar: `set PYTHONIOENCODING=utf-8` (CMD) ou `$env:PYTHONIOENCODING="utf-8"` (PowerShell). Logs em `logs/bot.log` permanecem UTF-8.

</details>

---

**Relacionado:** [COMMANDS_REFERENCE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/COMMANDS_REFERENCE.md) · [DEPLOY.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/DEPLOY.md)
