# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import ui, Interaction

# ===== CARREGAR VARIÁVEIS DE AMBIENTE =====
load_dotenv()

# ===== CONFIGURAÇÕES =====
TOKEN = os.getenv("DISCORD_TOKEN")
CATEGORIA_TICKETS_ID = 1432020375801397351
CATEGORIA_ANALISE_ID = 1434227754474886684
ADM_ROLE_ID = 1433844350848208976  # Cargo que pode aprovar/recusar

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.logs_channel_id = None



# ========= VIEW DE ANÁLISE =========
class AnaliseView(ui.View):
    def __init__(self, user: discord.Member, ticket_channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.user = user
        self.ticket_channel = ticket_channel

    @ui.button(label="✅ Aprovar", style=discord.ButtonStyle.success)
    async def aprovar(self, interaction: Interaction, button: ui.Button):
        if not any(role.id == ADM_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Você não tem permissão para aprovar.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Farm aprovado!", ephemeral=True)
        await self.ticket_channel.send(f"✅ {self.user.mention}, seu farm foi **aprovado e concluído com sucesso!** 🎉")

        await interaction.channel.send("✅ Farm aprovado. Canal de análise encerrado.")
        await interaction.channel.delete()

    @ui.button(label="❌ Negar", style=discord.ButtonStyle.danger)
    async def negar(self, interaction: Interaction, button: ui.Button):
        if not any(role.id == ADM_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Você não tem permissão para negar.", ephemeral=True)
            return

        await interaction.response.send_message("❌ Farm negado!", ephemeral=True)
        await self.ticket_channel.send(
            f"❌ {self.user.mention}, seu farm foi **recusado pela administração.** Você pode tentar novamente mais tarde."
        )

        await interaction.channel.send("❌ Farm negado. Canal de análise encerrado.")
        await interaction.channel.delete()


# ========= MODAL DE ENVIO DE FARM =========
class FarmModal(ui.Modal, title="📤 Enviar Farm"):
    descricao = ui.TextInput(label="Descrição do farm", style=discord.TextStyle.paragraph)
    quantidade = ui.TextInput(label="Quantidade", style=discord.TextStyle.short)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.send_message(
            "📸 Envie agora a **imagem do farm como anexo nesta conversa.**", ephemeral=True
        )

        def check(msg):
            return msg.author == interaction.user and msg.attachments

        try:
            msg = await bot.wait_for("message", timeout=120.0, check=check)
        except TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado! Tente novamente clicando em 📤 Enviar Farm.", ephemeral=True)
            return

        imagem = msg.attachments[0]
        guild = interaction.guild
        user = interaction.user

        categoria_analise = discord.utils.get(guild.categories, id=CATEGORIA_ANALISE_ID)
        if not categoria_analise:
            await interaction.followup.send("❌ Categoria de análise não encontrada.", ephemeral=True)
            return

        canal_analise = await guild.create_text_channel(
            name=f"analise-{user.name}",
            category=categoria_analise,
            topic=f"Análise do farm de {user.display_name}"
        )

        embed = discord.Embed(
            title="📩 Novo Farm Enviado",
            description=f"**Usuário:** {user.mention}\n**Descrição:** {self.descricao.value}\n**Quantidade:** {self.quantidade.value}",
            color=0x00b0f4
        )
        embed.set_image(url=imagem.url)

        view = AnaliseView(user, interaction.channel)
        await canal_analise.send(embed=embed, view=view)
        await interaction.followup.send("✅ Seu farm foi enviado para análise!", ephemeral=True)


# ========= VIEW PARA ENVIAR FARM =========
class FarmView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📤 Enviar Farm", style=discord.ButtonStyle.green)
    async def enviar_farm(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(FarmModal())


# ========= VIEW DO PAINEL =========
class PainelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📩 Abrir Ticket", style=discord.ButtonStyle.blurple)
    async def abrir_ticket(self, interaction: Interaction, button: ui.Button):
        categoria = discord.utils.get(interaction.guild.categories, id=CATEGORIA_TICKETS_ID)
        existente = discord.utils.get(interaction.guild.text_channels, name=f"💳┃ticket-{interaction.user.name.lower()}")
        if existente:
            await interaction.response.send_message("❗ Você já possui um ticket aberto.", ephemeral=True)
            return

        canal = await interaction.guild.create_text_channel(
            name=f"💳┃ticket-{interaction.user.name}",
            category=categoria,
            topic=f"Ticket de farm de {interaction.user.display_name}"
        )
        await canal.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await canal.set_permissions(interaction.guild.default_role, view_channel=False)

        boas_vindas = discord.Embed(
            title="👋 Bem-vindo ao seu ticket de farm!",
            description=(
                f"{interaction.user.mention}, envie aqui as informações do seu farm.\n\n"
                "📋 **Instruções:**\n"
                "1️⃣ Clique no botão **📤 Enviar Farm** abaixo.\n"
                "2️⃣ Preencha a descrição e a quantidade.\n"
                "3️⃣ Envie o print do farm como anexo aqui no chat.\n\n"
                "⏳ Após o envio, seu farm será analisado pela equipe administrativa."
            ),
            color=0x00b0f4
        )
        boas_vindas.set_footer(text="🕓 Equipe de Farm | Capello System")

        await canal.send(embed=boas_vindas, view=FarmView())
        await interaction.response.send_message(f"✅ Seu ticket foi criado: {canal.mention}", ephemeral=True)


# ========= COMANDO: CRIAR TICKET =========
@bot.command(name="criar_ticket")
async def criar_ticket(ctx, usuario: discord.Member):
    categoria = discord.utils.get(ctx.guild.categories, id=CATEGORIA_TICKETS_ID)
    if not categoria:
        await ctx.send("❌ Categoria de tickets não encontrada.")
        return

    canal = await ctx.guild.create_text_channel(
        name=f"💳┃ticket-{usuario.name}",
        category=categoria,
        topic=f"Ticket de farm de {usuario.display_name}"
    )
    await canal.set_permissions(usuario, view_channel=True, send_messages=True)
    await canal.set_permissions(ctx.guild.default_role, view_channel=False)

    boas_vindas = discord.Embed(
        title="👋 Bem-vindo ao seu ticket de farm!",
        description=(
            f"{usuario.mention}, envie aqui as informações do seu farm.\n\n"
            "📋 **Instruções:**\n"
            "1️⃣ Clique no botão **📤 Enviar Farm** abaixo.\n"
            "2️⃣ Preencha a descrição e a quantidade.\n"
            "3️⃣ Envie o print do farm como anexo aqui no chat.\n\n"
            "⏳ Após o envio, seu farm será analisado pela equipe administrativa."
        ),
        color=0x00b0f4
    )
    boas_vindas.set_footer(text="🕓 Equipe de Farm | Capello System")

    await canal.send(embed=boas_vindas, view=FarmView())
    await ctx.send(f"✅ Ticket criado: {canal.mention}")


# ========= COMANDO: PAINEL =========
@bot.command(name="painel")
async def painel(ctx):
    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Farm",
        description="Clique no botão abaixo para abrir seu ticket.",
        color=0x5865f2
    )
    view = PainelView()
    await ctx.send(embed=embed, view=view)


# ========= COMANDO: FECHAR TICKET =========
@bot.command(name="fechar_ticket")
async def fechar_ticket(ctx):
    if not ctx.channel.name.startswith("💳┃ticket-"):
        await ctx.send("❌ Este comando só pode ser usado em um ticket.")
        return
    await ctx.send("🗑️ Fechando ticket...")
    await ctx.channel.delete()


# ========= EVENTO DE INICIALIZAÇÃO =========
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    print("✨ Comandos prefixados com ! prontos para uso!")


bot.run(TOKEN)
