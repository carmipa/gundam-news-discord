"""
FilterDashboard view - Interactive button panel for filter configuration.
"""
import discord
from typing import Dict, Any, List
import logging

from core.filters import FILTER_OPTIONS
from utils.storage import load_config_cached, save_config_safe

log = logging.getLogger("MaftyIntel")


class FilterDashboard(discord.ui.View):
    """
    Painel persistente de filtros Mafty.
    Botões por categoria + botão de 'Ver filtros' + Reset.
    """
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = str(guild_id)
        self._rebuild()
    
    def _cfg(self) -> Dict[str, Any]:
        """Carrega config.json e garante estrutura mínima por guild."""
        cfg = load_config_cached({})
        if not isinstance(cfg, dict):
            log.error("config.json inválido. Recriando.")
            cfg = {}
        
        cfg.setdefault(self.guild_id, {"filters": [], "channel_id": None})
        
        if not isinstance(cfg[self.guild_id].get("filters"), list):
            cfg[self.guild_id]["filters"] = []
        
        return cfg
    
    def _save(self, cfg: Dict[str, Any]) -> None:
        save_config_safe(cfg)
    
    def _filters(self) -> List[str]:
        cfg = self._cfg()
        return list(cfg[self.guild_id].get("filters", []))
    
    def _set_filters(self, new_filters: List[str]) -> None:
        cfg = self._cfg()
        cfg[self.guild_id]["filters"] = list(dict.fromkeys(new_filters))
        self._save(cfg)
    
    def _is_admin(self, interaction: discord.Interaction) -> bool:
        """Somente admin altera filtros."""
        try:
            return bool(interaction.user.guild_permissions.administrator)
        except AttributeError as e:
            log.debug(f"Erro ao verificar permissões de admin (atributo ausente): {e}")
            return False
        except Exception as e:
            log.warning(f"Erro inesperado ao verificar permissões de admin: {e}")
            return False
    
    
    def _get_lang(self) -> str:
        cfg = self._cfg()
        return cfg[self.guild_id].get("language", "en_US")

    def _set_lang(self, lang_code: str) -> None:
        cfg = self._cfg()
        cfg[self.guild_id]["language"] = lang_code
        self._save(cfg)

    def _rebuild(self) -> None:
        """Reconstrói botões conforme filtros ativos."""
        self.clear_items()
        
        # --- SEÇÃO DE FILTROS ---
        active = set(self._filters())
        
        # Se "todos" está ativo, tudo deve parecer ativo visualmente
        everything_selected = "todos" in active
        
        for key, (label, emoji) in FILTER_OPTIONS.items():
            # A chave exata está ativa OU "todos" está ativo (visual apenas)
            is_active = (key in active) or everything_selected
            style = discord.ButtonStyle.success if is_active else discord.ButtonStyle.secondary
            
            btn = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=style,
                custom_id=f"mafty:filter:{self.guild_id}:{key}",
                row=0 if list(FILTER_OPTIONS.keys()).index(key) < 5 else 1 # Tenta organizar em linhas
            )
            btn.callback = self._toggle_callback
            self.add_item(btn)
        
        # --- SEÇÃO DE IDIOMA ---
        current_lang = self._get_lang()
        languages = {
            "en_US": "🇺🇸",
            "pt_BR": "🇧🇷",
            "es_ES": "🇪🇸",
            "it_IT": "🇮🇹",
            "ja_JP": "🇯🇵"
        }
        
        for code, flag in languages.items():
            style = discord.ButtonStyle.primary if code == current_lang else discord.ButtonStyle.secondary
            btn = discord.ui.Button(
                emoji=flag,
                style=style,
                custom_id=f"mafty:lang:{self.guild_id}:{code}",
                row=2 
            )
            btn.callback = self._lang_callback
            self.add_item(btn)

        # --- SEÇÃO DE CONTROLE ---
        show_btn = discord.ui.Button(
            label="Ver filtros",
            emoji="📌",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mafty:show:{self.guild_id}",
            row=3
        )
        show_btn.callback = self._show_callback
        self.add_item(show_btn)
        
        reset_btn = discord.ui.Button(
            label="Reset",
            emoji="🔄",
            style=discord.ButtonStyle.danger,
            custom_id=f"mafty:reset:{self.guild_id}",
            row=3
        )
        reset_btn.callback = self._reset_callback
        self.add_item(reset_btn)
    
    async def _toggle_callback(self, interaction: discord.Interaction):
        """Liga/desliga um filtro específico."""
        if not self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ Apenas administradores podem alterar filtros.",
                ephemeral=True
            )
            return
        
        # Extrai categoria do custom_id: "mafty:filter:123456:gunpla"
        parts = interaction.data.get("custom_id", "").split(":")
        if len(parts) < 4:
            await interaction.response.send_message("❌ Erro ao processar.", ephemeral=True)
            return
        
        category = parts[3]
        current = self._filters()
        msg = ""

        if category == "todos":
            # Lógica simples para o botão TUDO
            if "todos" in current:
                # Se já estava tudo, remover tudo? Ou limpar?
                # Vamos assumir toggle: se clica em TUDO e já está on, remove TUDO.
                current = []
                msg = "➖ **Filtro global removido.** (Nada selecionado)"
            else:
                # Liga TUDO, limpa o resto para ficar limpo
                current = ["todos"]
                msg = "🌟 **Modo TUDO ativado!**"
        
        else:
            # Categoria específica
            if "todos" in current:
                # SMART UNPACKING:
                # Se "todos" estava on e clicou em algo específico (ex: Gunpla),
                # o usuário quer "Tudo MENOS Gunpla".
                # Então: Remove "todos", adiciona TODAS as outras, menos a clicada.
                
                # Pega todas as chaves possíveis exceto "todos"
                all_cats = [k for k in FILTER_OPTIONS.keys() if k != "todos"]
                
                # Lista nova é tudo menos o que foi clicado
                new_list = [k for k in all_cats if k != category]
                
                current = new_list
                msg = f"➖ **{category.capitalize()}** removido (Modo TUDO desfeito)."
            
            else:
                # Comportamento padrão (toggle individual)
                if category in current:
                    current.remove(category)
                    msg = f"➖ **{category.capitalize()}** removido."
                else:
                    current.append(category)
                    msg = f"➕ **{category.capitalize()}** adicionado."
        
        self._set_filters(current)
        self._rebuild()
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(msg, ephemeral=True)

    async def _lang_callback(self, interaction: discord.Interaction):
        """Troca o idioma."""
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores.", ephemeral=True)
            return

        parts = interaction.data.get("custom_id", "").split(":")
        lang_code = parts[3]
        
        self._set_lang(lang_code)
        self._rebuild()
        
        flags = {"en_US": "🇺🇸", "pt_BR": "🇧🇷", "es_ES": "🇪🇸", "it_IT": "🇮🇹", "ja_JP": "🇯🇵"}
        flag = flags.get(lang_code, "🏳️")
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🌐 Idioma alterado para {flag} **{lang_code}**", ephemeral=True)

    async def _show_callback(self, interaction: discord.Interaction):
        """Mostra filtros ativos."""
        current = self._filters()
        if not current:
            await interaction.response.send_message(
                "📌 Nenhum filtro ativo. Todas as notícias estão bloqueadas.",
                ephemeral=True
            )
            return
        
        labels = [FILTER_OPTIONS.get(f, (f, ""))[0] for f in current]
        msg = "📌 **Filtros ativos:**\n" + "\n".join(f"• {lbl}" for lbl in labels)
        await interaction.response.send_message(msg, ephemeral=True)
    
    async def _reset_callback(self, interaction: discord.Interaction):
        """Reseta todos os filtros."""
        if not self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ Apenas administradores podem resetar filtros.",
                ephemeral=True
            )
            return
        
        self._set_filters([])
        self._rebuild()
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("🔄 Filtros resetados.", ephemeral=True)
