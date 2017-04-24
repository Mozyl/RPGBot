#!/usr/bin/env python3
# Copyright (c) 2016-2017, henry232323
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from discord.ext import commands
import discord
import asyncio
from .utils.data import Converter
from .utils import checks


class Economy(object):
    """Economy related commands: balance, market, etc"""
    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=["bal", "balance", "eco", "e"], no_pm=True, invoke_without_command=True)
    async def economy(self, ctx, member: discord.Member=None):
        """Check your or another users balance"""
        if member is None:
            member = ctx.author

        bal = await self.bot.di.get_balance(member)

        await ctx.send(f"{member.display_name} has {bal} Pokédollars")

    @checks.mod_or_permissions()
    @economy.command(aliases=["set"], no_pm=True)
    async def setbalance(self, ctx, amount: int, *members: Converter):
        """Set the balance of the given members to an amount"""
        if "everyone" in members:
            members = ctx.guild.members

        for member in members:
            await self.bot.di.set_eco(member, amount)

        await ctx.send("Balances changed")

    @checks.mod_or_permissions()
    @economy.command(aliases=["give"], no_pm=True)
    async def givemoney(self, ctx, amount: int, *members: Converter):
        """Give the members money (Moderators)"""
        if "everyone" in members:
            members = ctx.guild.members

        for member in members:
            await self.bot.di.add_eco(member, amount)

        await ctx.send("Money given")

    @commands.command(no_pm=True)
    async def pay(self, ctx, amount: int, member: discord.Member):
        """Pay another user money"""
        amount = abs(amount)
        await self.bot.di.add_eco(ctx.author, -amount)
        await self.bot.di.add_eco(member, amount)
        await ctx.send(f"Successfully paid {amount} Pokédollars to {member}")

    @commands.group(no_pm=True, aliases=["m", "pm"], invoke_without_command=True)
    async def market(self, ctx):
        """View the current market listings"""
        market = list((await self.bot.di.get_guild_market(ctx.guild)).items())
        desc = """
        \u27A1 to see the next page
        \u2B05 to go back
        \u274C to exit
        """
        if not market:
            await ctx.send("No items on the market to display.")
            return
        emotes = ("\u2B05", "\u27A1", "\u274C")
        embed = discord.Embed(description=desc, title="Player Market")
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)

        chunks = []
        for i in range(0, len(market), 25):
            chunks.append(market[i:i + 25])

        i = 0
        for item, value in chunks[i]:
            fmt = "\n".join(str(discord.utils.get(ctx.guild.members, id=x['user'])) + f": \u20BD{x['cost']} x{x['amount']}" for x in value)
            embed.add_field(name=item, value=fmt)

        max = len(chunks) - 1

        msg = await ctx.send(embed=embed)
        for emote in emotes:
            await msg.add_reaction(emote)

        while True:
            try:
                r, u = await self.bot.wait_for("reaction_add", check=lambda r, u: r.message.id == msg.id, timeout=80)
            except asyncio.TimeoutError:
                await ctx.send("Timed out! Try again")
                await msg.delete()
                return

            if u == ctx.guild.me:
                continue

            if u != ctx.author or r.emoji not in emotes:
                try:
                    await msg.remove_reaction(r.emoji, u)
                except:
                    pass
                continue

            if r.emoji == emotes[0]:
                if i == 0:
                    pass
                else:
                    embed.clear_fields()
                    i -= 1
                    for emote in emotes:
                        await msg.add_reaction(emote)

                    await msg.edit(embed=embed)

            elif r.emoji == emotes[1]:
                if i == max:
                    pass
                else:
                    embed.clear_fields()
                    i += 1
                    for emote in emotes:
                        await msg.add_reaction(emote)

                    await msg.edit(embed=embed)
            else:
                await msg.delete()
                await ctx.send("Closing")
                return

            try:
                await msg.remove_reaction(r.emoji, u)
            except:
                pass

    @market.command(no_pm=True, aliases=["createlisting", "new", "listitem", "list"])
    async def create(self, ctx, cost: int, amount: int, *, item: str):
        """Create a new market listing"""
        amount = abs(amount)
        cost = abs(cost)
        market = await self.bot.di.get_guild_market(ctx.guild)
        items = await self.bot.di.get_guild_items(ctx.guild)

        if item not in items:
            await ctx.send("That is not a valid item!")
            return

        if item not in market:
            market[item] = list()

        try:
            await self.bot.di.take_items(ctx.author, (item, amount))
        except ValueError:
            await ctx.send("You dont have enough of these to sell!")
            return

        for listing in market[item]:
            if listing["user"] == ctx.author.id and listing["cost"] == cost:
                listing["amount"] += amount
                break
        else:
            market[item].append(dict(user=ctx.author.id, cost=cost, amount=amount))

        await self.bot.di.update_guild_market(ctx.guild, market)

        await ctx.send("Item listed!")

    @market.command(no_pm=True, aliases=["purchase"])
    async def buy(self, ctx, amount: int, *, item: str):
        """Buy a given amount of an item from the player market at the cheapest given price"""
        amount = abs(amount)
        market = await self.bot.di.get_guild_market(ctx.guild)
        items = market.get(item)
        if not items:
            await ctx.send("There are none of those on the market! Sorry")
            return

        fcost = 0
        remaining = amount
        while remaining:
            m = min(items, key=lambda x: x.cost)
            if m.amount < remaining:
                items.remove(m)
                remaining -= m.amount
                fcost += m.amount * m.cost
            else:
                m.amount -= amount
                fcost += m.cost * amount

        try:
            await self.bot.di.add_eco(-fcost)
        except ValueError:
            await ctx.send("You cant afford this many!")
            return

        await self.bot.di.give_items(ctx.author, (item, amount))
        await self.bot.di.update_guild_market(ctx.guild, market)
        await ctx.send("Items successfully bought")
