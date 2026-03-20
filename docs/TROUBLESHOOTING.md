# 🧩 Troubleshooting

← [Voltar ao índice da documentação](README.md)

---

<details>
<summary><b>❌ CommandNotFound: Application command 'set_canal' not found</b></summary>

**Causa:** Sincronização global lenta do Discord.

**Solução:** O bot já faz sync por guild no `on_ready()`. Aguarde alguns segundos após o bot conectar.

</details>

<details>
<summary><b>❌ Bot não tem permissão para enviar mensagens</b></summary>

**Causa:** Bot não tem permissões no canal configurado.

**Solução:** 
1. Verifique as permissões do bot no servidor
2. Use `/set_canal` novamente - o bot verifica permissões automaticamente
3. Conceda as permissões: **Enviar Mensagens** e **Incorporar Links**

</details>

<details>
<summary><b>⚠️ "PyNaCl is not installed… voice will NOT be supported"</b></summary>

**Isso não é erro!** É apenas um aviso. O bot não usa recursos de voz, pode ignorar com segurança.

</details>

<details>
<summary><b>🔒 URL bloqueada por segurança</b></summary>

**Causa:** URL contém IP privado ou domínio local (proteção anti-SSRF).

**Solução:** Verifique se a URL em `sources.json` está correta e é pública.

</details>

<details>
<summary><b>⚠️ UnicodeEncodeError / emojis no console (Windows)</b></summary>

**Causa:** Terminal em encoding regional (ex.: cp1252) ao imprimir emojis nos logs.

**Solução:** O `utils/logger.py` usa stream UTF-8 no Windows quando possível. Se ainda falhar, defina antes de rodar: `set PYTHONIOENCODING=utf-8` (CMD) ou `$env:PYTHONIOENCODING="utf-8"` (PowerShell). Os logs em `logs/bot.log` permanecem em UTF-8.

</details>

---

**Relacionado:** [Referência de comandos](COMMANDS_REFERENCE.md) · [Deploy](DEPLOY.md)
