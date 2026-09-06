import discord
from discord import ui
import logging

logger = logging.getLogger(__name__)

class RosterStatusView(ui.View):
    def __init__(self, pco_client, service_type_id: str, plan_id: str, team_member_id: str):
        super().__init__(timeout=None)
        self.pco_client = pco_client
        self.service_type_id = service_type_id
        self.plan_id = plan_id
        self.team_member_id = team_member_id
        
        # We need custom IDs so Discord knows what button was pressed.
        # But for persistent views, custom IDs need to be unique to the component type, not dynamic per-message if we use `bot.add_view()`.
        # However, we can encode the data in the custom_id for dynamic handling in the future, or just let it timeout if the bot restarts.
        # For simplicity, we'll let it be tied to this specific view instance.
        # If the bot restarts, the buttons will stop working unless we register persistent views with dynamic parsing.
        # Given we are sending DMs, a non-persistent view might die on restart, but usually these are answered same-day.

    @ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        
        success = await self.pco_client.update_roster_status(
            str(self.service_type_id), 
            str(self.plan_id), 
            str(self.team_member_id), 
            "C" # Confirmed
        )
        
        if success:
            self.disable_all_items()
            await interaction.followup.edit_message(
                message_id=interaction.message.id, 
                content=interaction.message.content + "\n\n✅ **You have successfully Confirmed your schedule!**",
                view=self
            )
        else:
            await interaction.followup.send("⚠️ Failed to update your status. Please try again or log into Planning Center.", ephemeral=True)

    @ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        
        success = await self.pco_client.update_roster_status(
            str(self.service_type_id), 
            str(self.plan_id), 
            str(self.team_member_id), 
            "D" # Declined
        )
        
        if success:
            self.disable_all_items()
            await interaction.followup.edit_message(
                message_id=interaction.message.id, 
                content=interaction.message.content + "\n\n❌ **You have Declined your schedule.**",
                view=self
            )
        else:
            await interaction.followup.send("⚠️ Failed to update your status. Please try again or log into Planning Center.", ephemeral=True)

    def disable_all_items(self):
        for item in self.children:
            item.disabled = True
