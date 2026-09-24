import discord
import os
from discord.ext import commands
from pipeline import run_audit

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"MetaCheck is online as {bot.user}.")

@bot.command(name="audit")
@commands.has_permissions(administrator=True)
async def audit(ctx, url: str):
    await ctx.send(f"Processing verification for `{url}`...")
    
    try:
        video_id = url.split("v=")[-1].split("&")[0]
    except IndexError:
        await ctx.send("❌ Invalid YouTube URL.")
        return

    result = run_audit(video_id)
    
    if result.get("status") == "ERROR":
        await ctx.send(f"❌ **Error:** {result.get('message')}")
        return
        
    embed = discord.Embed(
        title="MetaCheck | Semantic Verification",
        description=f"**Target Entity:** {result['targets_detected']}",
        color=discord.Color.green() if result['status'] == 'VERIFIED' else discord.Color.red()
    )
    
    embed.add_field(name="Status", value=f"{'🟢 VERIFIED' if result['status'] == 'VERIFIED' else '🔴 REJECTED'}")
    embed.add_field(name="Information Density", value=f"{result['density']}%")
    
    skill = result.get('skill_metrics', {})
    embed.add_field(name="Skill Floor", value=f"{skill.get('composite_score', 'N/A')}/100 - {skill.get('difficulty_tag', 'N/A')}", inline=False)
    
    if result['violations']:
        embed.add_field(name="Contradictions Detected", value=f"{len(result['violations'])} violations found. Check Streamlit dashboard for details.", inline=False)

    await ctx.send(embed=embed)

@audit.error
async def audit_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🛑 **Permission Denied:** You must be a Server Administrator to run the MetaCheck backend.")

bot.run(os.getenv("DISCORD_TOKEN", "DISCORD_TOKEN_PLACEHOLDER"))