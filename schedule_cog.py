import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import logging

from utils import event_data, load_data, save_data, EVENT_PARAMS

logger = logging.getLogger('discord')

class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_event_reminders.start()

    def cog_unload(self):
        self.check_event_reminders.cancel()

    @tasks.loop(minutes=1)
    async def check_event_reminders(self):
        for event_name, data in event_data.items():
            params = EVENT_PARAMS.get(event_name)
            next_time_iso = data.get('next_time_iso')
            role_id = data.get('role_id')
            channel_id = data.get('channel_id')
            reminders_sent = data.get('reminders_sent', [])

            if not next_time_iso or not role_id or not channel_id or not params:
                continue
            
            try:
                next_time = datetime.fromisoformat(next_time_iso)
            except ValueError:
                logger.error(f"Invalid next_time_iso format for {event_name}: {next_time_iso}")
                continue

            now = datetime.now()
            
            reminders = [
                (timedelta(hours=1), '1 hour'),
                (timedelta(minutes=30), '30 minutes'),
                (timedelta(minutes=15), '15 minutes')
            ]

            for time_delta, reminder_text in reminders:
                reminder_time = next_time - time_delta
                
                if now > reminder_time and now < reminder_time + timedelta(seconds=60):
                    if reminder_text not in reminders_sent:
                        channel = self.bot.get_channel(channel_id)
                        
                        if channel:
                            role = channel.guild.get_role(role_id)
                            
                            if role:
                                try:
                                    await channel.send(
                                        f"{role.mention} 🔔 **{event_name}** is opening in **{reminder_text}**! "
                                        f"(Next event time: {next_time.strftime('%Y-%m-%d %H:%M UTC')})"
                                    )
                                    logger.info(f"Sent {reminder_text} reminder for {event_name}")
                                    data['reminders_sent'].append(reminder_text) 
                                    save_data() 
                                except discord.HTTPException as e:
                                    logger.error(f"Failed to send message for {event_name}: {e}")

            duration = params['duration']
            interval = params['interval']

            if now > next_time + duration and len(reminders_sent) > 0:
                new_time = next_time + interval
                data['next_time_iso'] = new_time.isoformat() 
                data['reminders_sent'] = []
                
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(
                        f"✅ **{event_name}** event is complete! "
                        f"The next opening time (in {interval.total_seconds() / 3600:.0f} hours) is: "
                        f"**{new_time.strftime('%Y-%m-%d %H:%M UTC')}**"
                    )
                save_data()
        
    @check_event_reminders.before_loop
    async def before_check_event_reminders(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setevent", description="Schedule the initial time, channel, and role for event reminders.")
    @app_commands.describe(
        event_name="Ancient_Ruins or Altar_of_Darkness",
        time_str="Event opening time (Format: YYYY-MM-DDTHH:MM, e.g., 2025-12-05T20:00)",
        role="The role to ping for reminders"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setevent_slash(self, interaction: discord.Interaction, event_name: str, time_str: str, role: discord.Role):
        
        event_name = event_name.replace('_', ' ').title() 
        
        if event_name not in event_data:
            valid_events = " or ".join([f"`{e.replace(' ', '_')}`" for e in event_data.keys()])
            await interaction.response.send_message(f"❌ Unknown event: `{event_name}`. Please use {valid_events}.", ephemeral=True)
            return

        try:
            next_time_dt = datetime.fromisoformat(time_str)
            if next_time_dt < datetime.now():
                await interaction.response.send_message("❌ The time specified is in the past. Please enter a future time.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use **YYYY-MM-DDTHH:MM** (e.g., `2025-12-05T20:00`).", ephemeral=True)
            return
        
        data = event_data[event_name]
        data['next_time_iso'] = next_time_dt.isoformat() 
        data['role_id'] = role.id
        data['channel_id'] = interaction.channel_id
        data['reminders_sent'] = [] 
        
        save_data()

        interval_hours = EVENT_PARAMS[event_name]['interval'].total_seconds() / 3600

        await interaction.response.send_message(
            f"✅ **{event_name}** is now scheduled for **{next_time_dt.strftime('%Y-%m-%d %H:%M UTC')}** "
            f"in this channel, tagging {role.mention}.\n"
            f"Reminders will be sent 1hr, 30m, and 15m prior. This event is set to repeat every **{interval_hours:.0f} hours**.",
            ephemeral=False
        )
        logger.info(f"Event {event_name} set by {interaction.user} for {next_time_dt.isoformat()}")

    @app_commands.command(name="checkevents", description="Displays the next scheduled time for all events.")
    async def checkevents_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(title="⏰ Current Event Schedules", description="Times are UTC.", color=discord.Color.blue())

        for event_name, data in event_data.items():
            time_iso = data.get('next_time_iso')
            channel_id = data.get('channel_id')
            role_id = data.get('role_id')
            
            interval_hours = EVENT_PARAMS.get(event_name, {}).get('interval', timedelta(hours=0)).total_seconds() / 3600

            if time_iso:
                try:
                    next_time = datetime.fromisoformat(time_iso)
                    
                    time_remaining = next_time - datetime.now()
                    
                    if time_remaining < timedelta(hours=-interval_hours):
                        status = "**Status:** Schedule is outdated (Please re-set initial time)."
                    elif time_remaining.total_seconds() < 0:
                        status = "**Status:** Event is currently open!"
                    else:
                        days = time_remaining.days if time_remaining.days > 0 else 0
                        hours, remainder = divmod(time_remaining.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        status = f"**Next:** {next_time.strftime('%Y-%m-%d %H:%M UTC')} (In {days}d {hours}h {minutes}m)"
                    
                    channel = self.bot.get_channel(channel_id)
                    channel_mention = channel.mention if channel else f"ID: {channel_id} (Missing)"
                    role_mention = f"<@&{role_id}>" if role_id else "N/A"
                    
                    embed.add_field(
                        name=f"🌟 {event_name}",
                        value=f"{status}\n"
                              f"**Interval:** Every {interval_hours:.0f} hours\n"
                              f"**Channel:** {channel_mention}\n"
                              f"**Role:** {role_mention}",
                        inline=False
                    )
                except ValueError:
                    embed.add_field(name=f"🌟 {event_name}", value="Error in scheduled time data format.", inline=False)
            else:
                 embed.add_field(name=f"🌟 {event_name}", value="Not yet scheduled.", inline=False)

        await interaction.followup.send(embed=embed)
