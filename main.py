#!/usr/bin/env python
# pyright: reportUnusedVariable=false, reportGeneralTypeIssues=false
import locale
import logging
import json
import os
from telegram import __version__ as TG_VER
from telegram import CallbackQuery, Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.error import BadRequest
from cdp import Cdp, Wallet, WalletData, wallet
import re
from decimal import Decimal
from replit import db
from web3 import Web3
import requests
from web3 import Account
import httpx
# Add the minimal ERC20 ABI for decimals()
ERC20_ABI = [{
    "constant": True,
    "inputs": [],
    "name": "decimals",
    "outputs": [{
        "name": "",
        "type": "uint8"
    }],
    "payable": False,
    "stateMutability": "view",
    "type": "function"
}, {
    "constant":
    False,
    "inputs": [{
        "name": "_spender",
        "type": "address"
    }, {
        "name": "_value",
        "type": "uint256"
    }],
    "name":
    "approve",
    "outputs": [{
        "name": "",
        "type": "bool"
    }],
    "payable":
    False,
    "stateMutability":
    "nonpayable",
    "type":
    "function"
}, {
    "constant":
    True,
    "inputs": [{
        "name": "_owner",
        "type": "address"
    }, {
        "name": "_spender",
        "type": "address"
    }],
    "name":
    "allowance",
    "outputs": [{
        "name": "",
        "type": "uint256"
    }],
    "payable":
    False,
    "stateMutability":
    "view",
    "type":
    "function"
}]
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def format_number(num):
    """
    Combine formatting for large numbers (k, M, B) and Indian number formatting.
    """
    if float(num) >= 1_000_000_000:
        return f"{float(num) / 1_000_000_000:.1f}B"  # Billion
    elif float(num) >= 1_000_000:
        return f"{float(num) / 1_000_000:.1f}M"  # Million
    elif float(num) >= 1_000:
        return f"{float(num) / 1_000:.1f}k"  # Thousand
    else:
        # Format using Indian number system
        if float(num) < 1:
            return f"{round(float(num),2)}"  # Return number as a decimal string for values less than 1
        formatted_number = locale.format_string("%.2f",
                                                round(float(num), 2),
                                                grouping=True)
        print(formatted_number, "formatted_number")
        return formatted_number


user_bot_name = "Velvet_Unicorn_bot"

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )

telegram_bot_token = os.environ['TELEGRAM_BOT_TOKEN']
cdp_api_key_name = os.environ['CDP_API_KEY_NAME']
cdp_api_key_private_key = os.environ['CDP_API_KEY_PRIVATE_KEY'].replace(
    '\\n', '\n')
encryption_key = os.environ['ENCRYPTION_KEY']

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def merge_token_arrays(array1, array2, update):
    """
    Merge two arrays dynamically to create a new array with specified fields.

    :param array1: List of tokens with market details
    :param array2: List of tokens with wallet details
    :return: Merged list of tokens
    """
    merged_array = []

    w3 = Web3(
        Web3.HTTPProvider(
            'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
        ))
    wallet = await get_or_create_address(update)
    owner_address = wallet.address_id

    for item2 in array2:
        for item1 in array1:
            # Match tokens based on token address
            token_address = item2['tokenAddress'].lower()
            if token_address == '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':
                token_address = '0x4200000000000000000000000000000000000006'
            if token_address == item1['token']['address'].lower():

                if item2['tokenAddress'].lower(
                ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                    balance_wei = w3.eth.get_balance(
                        Web3.to_checksum_address(owner_address)
                    )  # Use the owner's address for ETH balance
                    balance = w3.from_wei(balance_wei, 'ether')
                else:
                    balance = Decimal(
                        wallet.balance(
                            Web3.to_checksum_address(item2['tokenAddress'])))

                merged_array.append({
                    'tokenAddress': item2['tokenAddress'],
                    'tokenName': item2['tokenName'],
                    'oldPrice': item2['tokenAmount'],
                    'newPrice': item1['priceUSD'],
                    "marketCap": item1['marketCap'],
                    "liquidity": item1['liquidity'],
                    "holders": item1['holders'],
                    "change1": item1['change1'],
                    "change24": item1['change24'],
                    "balance": str(balance)
                })

    # Filter out zero balance items from merged_array
    filtered_array = [
        item for item in merged_array if float(item['balance']) != 0
    ]

    return filtered_array


def fetch_price_from_codex(tokens, chain):
    print(f"🚀 ~ fetch_price_from_codex ~ tokens: {tokens}, chain: {chain}")
    try:
        # Format tokens as a string suitable for the GraphQL query
        token_inputs = '\n'.join([f'"{token}"' for token in tokens])
        print(f"🚀 ~ fetch_price_from_codex ~ tokenInputs: {token_inputs}")

        # GraphQL query
        query = f"""
        query {{
          filterTokens(
            tokens: [{token_inputs}],
            limit: 200
          ) {{
            results {{
              token {{
                address
                decimals
                name
                networkId
                symbol
              }}
              marketCap
              holders
              priceUSD
              liquidity
              change1
              change24
              createdAt
            }}
          }}
        }}
        """

        # Request headers
        headers = {
            "Authorization": "e1d573dd2d5992e65c8fc67cb73dca5229e4aca5",
            "Content-Type": "application/json",
        }

        # Make the POST request
        response = requests.post(
            "https://graph.defined.fi/graphql",
            json={"query": query},
            headers=headers,
        )

        # Raise an exception if the response contains an HTTP error
        response.raise_for_status()

        # Extract data from the response
        price_data = response.json()
        filter_tokens = price_data.get("data", {}).get("filterTokens",
                                                       {}).get("results", [])
        return filter_tokens

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch price from codex: {str(e)}")
        return []


# TODO: This should be typed.
async def get_or_create_address(update: Update):
    """Get or create an address for the bot."""
    logging.info("Starting get_or_create_address function")
    user_id = str(update.effective_user.id)
    logging.info(f"User ID: {user_id}")

    if user_id in db:
        logging.info("User data found in db")
        # If user data exists in db, decrypt and import the wallet
        encrypted_data = db[user_id]
        logging.info("Retrieved encrypted data from db")
        stored_data = json.loads(encrypted_data)
        logging.info("Parsed stored data")
        decrypted_data = decrypt(stored_data['encrypted'], stored_data['iv'])
        logging.info("Decrypted data")
        wallet_data = WalletData.from_dict(decrypted_data)
        logging.info("Created WalletData object")
        wallet = Wallet.import_data(wallet_data)
        logging.info("Imported wallet data")
    else:
        logging.info("User data not found in db, creating new wallet")
        # If user data doesn't exist, create a new wallet
        wallet = Wallet.create("base-mainnet")
        logging.info("Created new wallet")
        wallet_data = wallet.export_data()
        logging.info("Exported wallet data")

        # Generate a new IV and encrypt the wallet data
        iv = os.urandom(16).hex()  # Generate a 16-byte IV and convert to hex
        logging.info("Generated new IV")
        encrypted_data = encrypt(wallet_data.to_dict(), iv)
        logging.info("Encrypted wallet data")

        # Save the encrypted wallet data and IV to db
        db[user_id] = json.dumps({'encrypted': encrypted_data, 'iv': iv})
        logging.info("Saved encrypted wallet data to db")

    logging.info("Returning wallet default address")
    return wallet.default_address


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    try:
        address = await get_or_create_address(update)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")
        return
    args = context.args
    print(args, "args")
    referral_user = None

    if args and args[0].startswith('ref-'):
        referral_user = args[0].split('-')[1]

    # Simulating user data
    user_id = update.effective_user.id
    user_name = update.effective_user.username
    wallet_address = address.address_id.lower()
    keyboard = [
        [
            # InlineKeyboardButton("Check Balance",
            #                      callback_data='check_balance'),
            InlineKeyboardButton("Buy", callback_data='trade_token_sell'),
            InlineKeyboardButton("Sell", callback_data='trade_token_buy')
        ],
        [
            InlineKeyboardButton("Positions", callback_data='my_position'),
            InlineKeyboardButton("Deposit", callback_data='deposit_eth'),
            InlineKeyboardButton("Withdraw", callback_data='withdraw_eth'),
        ],
        [
            InlineKeyboardButton("Balance", callback_data='check_balance'),
            InlineKeyboardButton("Export", callback_data='export_key')
        ],
        [InlineKeyboardButton("Referral", callback_data='referral')],
        # [InlineKeyboardButton("Pin message", callback_data='pin_message')],
        [
            InlineKeyboardButton("Trade",
                                 callback_data='trade')  # New Trade button
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Welcome to your Onchain Trading Bot!\n"
        f"Your Base address is:\n"
        f"`{wallet_address}` (Tap to copy)\n"
        f"Select an option below:",
        reply_markup=reply_markup,
        parse_mode="Markdown")

    api_url_add_user = "https://tbotserver.velvetdao.xyz/add-user"

    add_user_payload = {
        "userId": user_id,
        "userName": user_name,
        "walletAddress": wallet_address,
    }
    try:
        response = requests.post(api_url_add_user, json=add_user_payload)
        if response.status_code == 201:
            print("user added")
        else:
            print("fail user added")
    except Exception as e:
        await update.message.reply_text(f"Failed to record User: {str(e)}")
    if referral_user:
        print({
            "userId": user_id,
            "userName": user_name,
            "walletAddress": wallet_address,
            "referralUser": referral_user
        })
        api_url = "https://tbotserver.velvetdao.xyz/add-referred-user"
        payload = {
            "userId": user_id,
            "userName": user_name,
            "walletAddress": wallet_address,
            "referralUser": referral_user
        }

        try:
            response = requests.post(api_url, json=payload)
            if response.status_code == 201:
                await update.message.reply_text(
                    "Referral successfully recorded.")
            else:
                await update.message.reply_text("Failed to record referral.")
        except Exception as e:
            await update.message.reply_text(
                f"Error recording referral: {str(e)}")


async def check_balance(update: Update) -> dict:
    """Get the balances for the wallet."""
    wallet = await get_or_create_address(update)
    return wallet.balances()


def is_valid_eth_address(address):
    # Check if it's a valid hexadecimal Ethereum address
    if Web3.is_address(address):
        return True

    # Check if it's a valid .base.eth or .eth domain
    if re.match(r'^[a-zA-Z0-9-]+\.base\.eth$', address) or re.match(
            r'^[a-zA-Z0-9-]+\.eth$', address):
        return True

    return False


async def handle_button_referral(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Generate Referral Link' button press."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    user_id = str(update.effective_user.id)
    referral_base_url = f"https://t.me/{user_bot_name}?start=ref"
    referral_link = f"{referral_base_url}-{user_id}"

    # Check current referral points
    user_points = 0

    # Send referral details and the link
    await message.reply_text(
        f"🌟 **Referral Program** 🌟\n\n"
        f"Become Velvet Unicorn co-founder - refer new users and earn 50% of their trading fees! 🏆\n\n"
        f"Here is your unique referral link:\n\n"
        f"`{referral_link}`\n\n"
        f"Share this link and start earning now!  🚀",
        parse_mode="Markdown")


async def handle_my_position(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Handle the My Position button click."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    await message.reply_text("Fetching your current token positions...")
    try:
        # Call the API to get tokens
        w3 = Web3(
            Web3.HTTPProvider(
                'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
            ))
        wallet = await get_or_create_address(update)
        wallet_address = wallet.address_id
        chain = 8453
        print(f"🚀 ~ handle_my_position ~ wallet_address: {wallet_address}")
        balance_wei = w3.eth.get_balance(
            Web3.to_checksum_address(
                wallet_address))  # Use the owner's address for ETH balance
        balance = w3.from_wei(balance_wei, 'ether')
        chain = 8453
        tokens = [f"0x4200000000000000000000000000000000000006:{chain}"]
        price_data = fetch_price_from_codex(tokens, chain)
        price = price_data[0]['priceUSD']
        response = requests.get(
            "https://tbotserver.velvetdao.xyz/get-token",
            params={'walletAddress': wallet_address.lower()})
        if response.status_code == 200:
            data = response.json()
            print(data)
            tokens = data.get('tokens', [])
            token_addresses = [
                f"{token['tokenAddress']}:{chain}" if token['tokenAddress']
                != "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else
                f"0x4200000000000000000000000000000000000006:{chain}"
                for token in tokens
            ]
            print(
                f"🚀 ~ handle_my_position ~ token_addresses: {token_addresses}")
            price_data = fetch_price_from_codex(token_addresses, chain)
            print(f"🚀 ~ handle_my_position ~ price_data: {price_data}")
            merge_array = await merge_token_arrays(price_data, tokens, update)
            print(f"🚀 ~ handle_my_position ~ merge_array: {merge_array}")

            if merge_array:
                messages = (
                    f"Wallet: `{wallet_address}`\n\n"
                    f"ETH Balance:`{balance}` ETH (${format_number(float(balance) * float(price))}) \n\n"
                )
                for token in merge_array:
                    # Skip if the tokenAddress is "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
                    if token[
                            'tokenAddress'] == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                        continue
                    messages += (
                        f"{token['tokenName']} -"
                        f"[📈](https://www.dextools.io/app/en/base/pair-explorer/{token['tokenAddress']})"
                        f"**{round(float(token['balance']),6)} (${format_number(float(token['balance']) * float(token['newPrice']))})**\n"
                        f"• `{token['tokenAddress']}`\n"
                        f"• Price & MC: **${format_number(float(token['newPrice']))}** — **${format_number(token['marketCap'])}** \n"

                        # — **{format_number(token['liquidity'])}**
                        f"• Average entry: **${format_number((float(token['oldPrice']) + float(token['newPrice'])) /2)}** — **${format_number(token['marketCap'])}**\n"
                        f"• Liquidity: ${format_number(token['liquidity'])}\n\n\n"
                    )
            else:
                messages = "No current positions found."
        else:
            messages = f"Error: {response.json().get('error', 'Unknown error')}"

    except Exception as e:
        messages = f"Error fetching token details: {str(e)}"

    await message.reply_text(messages, parse_mode='Markdown')


async def handle_button_check_balance(
        update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Check Balance' action from both button click and command."""

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    elif update.message:
        message = update.message
    else:
        return

    await message.reply_text("Your balances are as follows:")

    try:
        balances = await check_balance(update)

        if len(balances) == 0:
            balance_message = "No balances."
        else:
            balance_message = "\n".join(
                [f"{token}: {amount}" for token, amount in balances.items()])

        await message.reply_text(balance_message)

    except Exception as e:
        # Handle any errors
        await message.reply_text(f"Error retrieving balances: {str(e)}")


async def handle_button_deposit_eth(
        update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Deposit ETH' button press."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return

    await message.reply_text(
        "Send your ETH to the following address on Base Mainnet:")
    try:
        wallet = await get_or_create_address(update)
        deposit_address = wallet.address_id
        await message.reply_text(deposit_address)
    except Exception as e:
        await message.reply_text(f"Error retrieving deposit address: {str(e)}")


async def handle_button_withdraw_eth(
        update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Withdraw ETH' button press."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    await message.reply_text("How much ETH would you like to withdraw?",
                             reply_markup=ForceReply())
    context.user_data['awaiting_withdraw_amount'] = True


async def handle_button_export_key(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Export Key' button press."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    await message.reply_text(
        "The following contains your private key. Keep it somewhere private and do not share it with anyone."
    )
    try:
        wallet = await get_or_create_address(update)
        private_key = wallet.key.key.hex()
        await message.reply_text(f"`{private_key}`", parse_mode='MarkdownV2')
    except Exception as e:
        await message.reply_text(f"Error exporting private key: {str(e)}")


async def handle_button_pin_message(
        query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Pin message' button press."""
    try:
        await context.bot.pin_chat_message(chat_id=query.message.chat_id,
                                           message_id=query.message.message_id)
        await query.message.reply_text("Message pinned successfully!")
    except BadRequest as e:
        await query.message.reply_text(f"Failed to pin message: {str(e)}")


async def handle_button_buy(query: CallbackQuery,
                            context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Buy' button press."""
    await query.message.reply_text(
        "How much ETH would you like to spend on the buy?",
        reply_markup=ForceReply())
    context.user_data['awaiting_buy_amount'] = True


async def handle_button_sell(query: CallbackQuery,
                             context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Sell' button press."""
    await query.message.reply_text(
        "Which asset would you like to sell? (contract address)",
        reply_markup=ForceReply())
    context.user_data['awaiting_sell_asset'] = True


async def handle_trade_no(update: Update, query: CallbackQuery) -> None:
    """Handle the 'No' button press."""
    try:
        address = await get_or_create_address(update)

        keyboard = [
            [
                # InlineKeyboardButton("Check Balance",
                #                      callback_data='check_balance'),
                InlineKeyboardButton("Buy", callback_data='trade_token_sell'),
                InlineKeyboardButton("Sell", callback_data='trade_token_buy'),
            ],
            [
                InlineKeyboardButton("Positions", callback_data='my_position'),
                InlineKeyboardButton("Deposit", callback_data='deposit_eth'),
                InlineKeyboardButton("Withdraw", callback_data='withdraw_eth'),
            ],
            [
                InlineKeyboardButton("Balance", callback_data='check_balance'),
                InlineKeyboardButton("Export", callback_data='export_key')
            ],
            [InlineKeyboardButton("Referral", callback_data='referral')],
            # [InlineKeyboardButton("Pin message", callback_data='pin_message')],
            [
                InlineKeyboardButton("Trade",
                                     callback_data='trade')  # New Trade button
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Welcome to your Onchain Trading Bot!\n"
            f"Your Base address is:\n"
            f"`{address.address_id}` (Tap to copy)\n"
            f"Select an option below:",
            reply_markup=reply_markup,
            parse_mode="Markdown")
    except Exception as e:
        logging.error(f"An error occurred in handle_trade_no: {str(e)}")
        await query.message.reply_text(
            "An error occurred. Please try again later.")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button press and sends a new message."""
    query = update.callback_query
    await query.answer()

    if query.data == 'check_balance':
        await handle_button_check_balance(update, context)
    elif query.data == 'referral':
        await handle_button_referral(update, context)
    elif query.data == 'trade':
        await handle_button_trade(update, context)
    elif query.data == '25_amount':
        await handle_amount_to_trade(update, context, query, 25)
    elif query.data == '50_amount':
        await handle_amount_to_trade(update, context, query, 50)
    elif query.data == '75_amount':
        await handle_amount_to_trade(update, context, query, 75)
    elif query.data == '100_amount':
        await handle_amount_to_trade(update, context, query, 100)
    elif query.data == '0.05_amount':
        await handle_amount_to_trade_number(update, context, query, 0.05)
    elif query.data == '0.1_amount':
        await handle_amount_to_trade_number(update, context, query, 0.1)
    elif query.data == '0.3_amount':
        await handle_amount_to_trade_number(update, context, query, 0.3)
    elif query.data == '0.5_amount':
        await handle_amount_to_trade_number(update, context, query, 0.5)
    elif query.data == '5_slippage':
        await handle_slippage(update, context, 5)
    elif query.data == '3_slippage':
        await handle_slippage(update, context, 3)
    elif query.data == '2_slippage':
        await handle_slippage(update, context, 2)
    elif query.data == '1_slippage':
        await handle_slippage(update, context, 1)
    elif query.data == 'x_amount':
        await handle_x_amount(update, context, query)
    elif query.data == 'x_slippage':
        await handle_x_slippage(update, context)
    elif query.data == 'deposit_eth':
        await handle_button_deposit_eth(update, context)
    elif query.data == 'withdraw_eth':
        await handle_button_withdraw_eth(update, context)
    elif query.data == 'export_key':
        await handle_button_export_key(update, context)
    elif query.data == 'pin_message':
        await handle_button_pin_message(query, context)
    elif query.data == 'buy':
        await handle_button_buy(query, context)
    elif query.data == 'sell':
        await handle_button_sell(query, context)
    elif query.data == 'trade_yes':
        await handle_trade_confirmation(update, context, query)
    elif query.data == 'trade_no':
        await handle_trade_no(update, query)
    elif query.data == 'my_position':
        await handle_my_position(update, context)
    elif query.data == 'trade_token_buy':
        await handle_trade_token_buy(update, context)
    elif query.data == 'trade_token_sell':
        await handle_trade_token_sell(update, context)
    elif query.data == 'trade_token_amount_click':
        await handle_trade_amount_click(update, context, query)

    else:
        await query.message.reply_text(f"You selected {query.data}")


async def handle_slippage(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          slippage) -> None:
    """Print the slippage value."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return

    try:
        context.user_data['slippage_for_trade'] = slippage
        print(f'Slippage set : {slippage}')
        await message.reply_text(f'Slippage set: {slippage}',
                                 parse_mode="Markdown")
    except Exception as e:
        print(f"An error occurred while handling slippage: {str(e)}")


async def handle_x_slippage(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask user to enter slippage value and store it."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return

    try:
        # Prompt the user to enter the slippage value
        await message.reply_text("Please enter the slippage value:",
                                 reply_markup=ForceReply())

        # Replace the erroneous wait_for with the event loop listening for a message
        user_response = await context.update_queue.get()
        try:
            slippage = (user_response.message.text.strip())
        except ValueError:
            await message.reply_text(
                'Please enter a valid number for slippage.')
            return
        context.user_data['slippage_for_trade'] = slippage
        print(f'Slippage manually set: {slippage}')

        # Confirm the slippage has been set to the user
        await message.reply_text(f'Slippage set: {slippage}',
                                 parse_mode="Markdown")
    except Exception as e:
        print(f"An error occurred while handling slippage: {str(e)}")


async def handle_x_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: CallbackQuery,
) -> None:
    """Ask user to enter slippage value and store it."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    try:
        # Ask the user for the amount to trade

        user_input = await message.reply_text(
            "Please enter the amount you wish to trade:",
            reply_markup=ForceReply())

        context.user_data['awaiting_x_amount'] = True

    except Exception as e:
        print(f"An error occurred while handling amount: {str(e)}")


async def handling_x_amount(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask user to enter slippage value and store it."""
    context.user_data['awaiting_x_amount'] = False

    try:
        text = update.message.text.strip()
        print(text, "text")
        trade_message = (f"*Selected amount to trade*: `{text}`\n\n")

        await update.message.reply_text(trade_message,
                                        reply_markup=ForceReply(),
                                        parse_mode="Markdown")
        context.user_data['amount_to_trade'] = Decimal(text)

        await handle_trade_amount(update, context)

    except Exception as e:
        print(f"An error occurred while handling amount: {str(e)}")


async def handle_amount_to_trade(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE,
                                 query: CallbackQuery, percentage) -> None:
    """Handle new handle_amount_to_trade"""
    context.user_data['awaiting_trade_amount'] = True
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return

    try:
        print(percentage)
        w3 = Web3(
            Web3.HTTPProvider(
                'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
            ))

        sell_token = Web3.to_checksum_address(
            context.user_data['trade_sell_token'])
        buy_token = Web3.to_checksum_address(
            context.user_data['trade_buy_token'])

        wallet = await get_or_create_address(update)
        owner_address = wallet.address_id
        if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
            balance_wei = w3.eth.get_balance(
                Web3.to_checksum_address(
                    owner_address))  # Use the owner's address for ETH balance
            balance = w3.from_wei(balance_wei, 'ether')
        else:
            balance = Decimal(wallet.balance(sell_token))
        print(f"🚀 ~ handle_amount_to_trade ~ balance: {balance}", percentage)
        if percentage == 100:
            balance_percentage = (balance)
        else:
            balance_percentage = ((percentage / 100) * float(balance))
        print(balance_percentage)
        context.user_data['amount_to_trade'] = balance_percentage
        # if query.message:
        #     await handle_trade_amount(update, context, query)
        # else:
        #     await update.message.reply_text("Error: trade amount could not be processed.")
        trade_message = (
            f"💼 *{percentage}% of {balance} *\n\n"
            f"*Selected amount to trade*: `{balance_percentage}`\n\n")

        await message.reply_text(trade_message,
                                 reply_markup=ForceReply(),
                                 parse_mode="Markdown")
        await handle_trade_amount_click(update, context, query)

    except Exception as e:
        print(f"An error occurred: {str(e)}")


async def handle_amount_to_trade_number(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE,
                                        query: CallbackQuery,
                                        amount_to_trade: float) -> None:
    """Handle new handle_amount_to_trade"""
    context.user_data['awaiting_trade_amount'] = True
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return

    try:

        w3 = Web3(
            Web3.HTTPProvider(
                'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
            ))

        sell_token = Web3.to_checksum_address(
            context.user_data['trade_sell_token'])
        buy_token = Web3.to_checksum_address(
            context.user_data['trade_buy_token'])

        wallet = await get_or_create_address(update)
        owner_address = wallet.address_id
        if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
            balance_wei = w3.eth.get_balance(
                Web3.to_checksum_address(owner_address))
            balance = w3.from_wei(balance_wei, 'ether')
        else:
            balance = Decimal(wallet.balance(sell_token))

        if amount_to_trade > balance:
            await message.reply_text("Not enough balance to execute trade.")
            return
        context.user_data['amount_to_trade'] = amount_to_trade

        trade_message = (
            f"*Selected amount to trade *: `{amount_to_trade}`\n\n")

        await message.reply_text(trade_message,
                                 reply_markup=ForceReply(),
                                 parse_mode="Markdown")
        await handle_trade_amount_click(update, context, query)

    except Exception as e:
        print(f"An error occurred during handle_amount_to_trade: {str(e)}")


async def handle_withdraw_amount(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the withdrawal amount input."""
    try:
        text = update.message.text.strip()
        if not re.match(r'^\d*\.?\d+$', text):
            raise ValueError("Invalid decimal format")
        amount = Decimal(text)
        wallet = await get_or_create_address(update)
        balance = Decimal(wallet.balance('eth'))

        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount.")
        elif amount > balance:
            await update.message.reply_text(
                f"Insufficient balance. Your current ETH balance is {balance}."
            )
        else:
            context.user_data['withdraw_amount'] = amount
            context.user_data['awaiting_withdraw_address'] = True
            context.user_data['awaiting_withdraw_amount'] = False
            await update.message.reply_text(
                "Please enter the Ethereum address to withdraw to:",
                reply_markup=ForceReply())
    except ValueError:
        await update.message.reply_text(
            "Invalid amount. Please enter a valid number.")


async def handle_withdraw_address(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the withdrawal address input."""
    address = update.message.text
    if is_valid_eth_address(address):
        amount = context.user_data['withdraw_amount']
        wallet = await get_or_create_address(update)

        waiting_message = await update.message.reply_text(
            "Waiting for withdrawal to complete...")

        try:
            transfer = wallet.transfer(amount, 'eth', address).wait()
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id)
            await update.message.reply_text(
                f"Withdrawal complete! Transaction link: {transfer.transaction_link}"
            )
        except Exception as e:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id)
            await update.message.reply_text(f"Withdrawal failed: {str(e)}")

        context.user_data['awaiting_withdraw_address'] = False
        context.user_data.pop('withdraw_amount', None)
    else:
        await update.message.reply_text(
            "Invalid Ethereum address. Please enter a valid address.")


async def handle_buy_amount(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the buy amount input."""
    try:
        text = update.message.text.strip()
        if not re.match(r'^\d*\.?\d+$', text):
            raise ValueError("Invalid decimal format")
        amount = Decimal(text)
        wallet = await get_or_create_address(update)
        balance = Decimal(wallet.balance('eth'))

        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount.")
        elif amount > balance:
            await update.message.reply_text(
                f"Insufficient balance. Your current ETH balance is {balance}."
            )
        else:
            context.user_data['buy_amount'] = amount
            context.user_data['awaiting_buy_asset'] = True
            context.user_data['awaiting_buy_amount'] = False
            await update.message.reply_text(
                "Please enter the asset you'd like to buy (contract address):",
                reply_markup=ForceReply())
    except ValueError:
        await update.message.reply_text(
            "Invalid amount. Please enter a valid number.")


async def handle_buy_asset(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the buy asset input."""
    asset = update.message.text
    amount = context.user_data['buy_amount']
    wallet = await get_or_create_address(update)

    waiting_message = await update.message.reply_text("Executing buy...")

    try:
        trade = wallet.trade(amount, 'eth', asset).wait()
        await context.bot.delete_message(chat_id=update.effective_chat.id,
                                         message_id=waiting_message.message_id)
        await update.message.reply_text(
            f"Buy successfully completed! Transaction link: {trade.transaction.transaction_link}"
        )
    except Exception as e:
        await context.bot.delete_message(chat_id=update.effective_chat.id,
                                         message_id=waiting_message.message_id)
        await update.message.reply_text(f"Buy failed: {str(e)}")

    context.user_data['awaiting_buy_asset'] = False
    context.user_data.pop('buy_amount', None)


async def handle_sell_asset(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the sell asset input."""
    asset = update.message.text
    context.user_data['sell_asset'] = asset
    context.user_data['awaiting_sell_asset'] = False
    context.user_data['awaiting_sell_amount'] = True
    await update.message.reply_text(
        f"How much {asset} would you like to sell?", reply_markup=ForceReply())


async def handle_sell_amount(update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the sell amount input."""
    try:
        text = update.message.text.strip()
        if not text or not text.replace('.', '', 1).isdigit():
            raise ValueError("Invalid decimal format")
        amount = Decimal(text)
        asset = context.user_data['sell_asset']
        print(asset)
        wallet = await get_or_create_address(update)
        balance = Decimal(wallet.balance(asset))

        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount.")
        elif amount > balance:
            await update.message.reply_text(
                f"Insufficient balance. Your current {asset} balance is {balance}."
            )
        else:
            waiting_message = await update.message.reply_text(
                "Executing sell...")

            try:
                trade = wallet.trade(amount, asset, 'eth').wait()
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=waiting_message.message_id)
                await update.message.reply_text(
                    f"Sell successfully completed! Transaction link: {trade.transaction.transaction_link}"
                )
            except Exception as e:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=waiting_message.message_id)
                await update.message.reply_text(f"Sell failed: {str(e)}")

            context.user_data['awaiting_sell_amount'] = False
            context.user_data.pop('sell_asset', None)
    except ValueError:
        await update.message.reply_text(
            "Invalid amount. Please enter a valid number.")


async def handle_trade_token_buy(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the sell token input."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    buy_token = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"

    context.user_data['trade_buy_token'] = buy_token
    context.user_data['awaiting_trade_sell_token_auto'] = True
    await message.reply_text(
        "Enter the token you want to sell (contract address):",
        reply_markup=ForceReply())


async def handle_trade_token_sell(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the sell token input."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    sell_token = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    context.user_data['trade_sell_token'] = sell_token
    context.user_data['awaiting_trade_sell_token'] = False
    context.user_data['awaiting_trade_buy_token'] = True
    await message.reply_text(
        "Enter the token you want to buy (contract address):",
        reply_markup=ForceReply())


async def handle_button_trade(update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Trade' button press."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(
            "Enter the token you want to sell (contract address):",
            reply_markup=ForceReply())
    elif update.message:
        await update.message.reply_text(
            "Enter the token you want to sell (contract address):",
            reply_markup=ForceReply())
    context.user_data['awaiting_trade_sell_token'] = True


async def handle_trade_sell_token(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the sell token input."""
    sell_token = update.message.text
    # Check if the sell_token is a valid address
    if not Web3.is_address(sell_token):
        await update.message.reply_text("Please provide a valid address.")
        return
    context.user_data['trade_sell_token'] = sell_token
    context.user_data['awaiting_trade_sell_token'] = False
    context.user_data['awaiting_trade_buy_token'] = True
    await update.message.reply_text(
        "Enter the token you want to buy (contract address):",
        reply_markup=ForceReply())


async def handle_trade_buy_token(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the buy token input."""
    buy_token = update.message.text
    if not Web3.is_address(buy_token):
        await update.message.reply_text("Please provide a valid address.")
        return
    context.user_data['trade_buy_token'] = buy_token
    context.user_data['awaiting_trade_buy_token'] = False
    context.user_data['slippage_for_trade'] = "5"
    # Create a Web3 instance using HTTPProvider
    w3 = Web3(
        Web3.HTTPProvider(
            'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
        ))

    # Convert the sell token from context to a checksum address
    sell_token = Web3.to_checksum_address(
        context.user_data['trade_sell_token'])
    print(f"Sell token checksum address: {sell_token}")

    # Convert the buy token from the user's message text to a checksum address
    buy_token_new = Web3.to_checksum_address(update.message.text)
    print(f"Buy token checksum address: {buy_token_new}")

    # Obtain the user's wallet, or create one if it doesn't exist
    wallet = await get_or_create_address(update)
    owner_address = wallet.address_id

    # Fetch and compute balance depending on the token type
    if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
        balance_wei = w3.eth.get_balance(
            Web3.to_checksum_address(
                owner_address))  # Use the owner's address for ETH balance
        balance = w3.from_wei(balance_wei, 'ether')


# Convert balance from wei to ether
    else:
        balance = Decimal(wallet.balance(sell_token))  # Fetch token balance
    print(f"Balance: {balance}")

    chain = 8453
    tokens = [
        f"0x4200000000000000000000000000000000000006:{chain}"
        if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        else f"{Web3.to_checksum_address(sell_token)}:{chain}",
        f"0x4200000000000000000000000000000000000006:{chain}"
        if buy_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        else f"{Web3.to_checksum_address(buy_token)}:{chain}"
    ]

    price_data = fetch_price_from_codex(tokens, chain)

    sell_token_tocheck = "0x4200000000000000000000000000000000000006" if sell_token.lower(
    ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else sell_token

    if price_data[0]['token']['address'].lower() == sell_token_tocheck.lower():
        sell_element = price_data[0]
        buy_element = price_data[1]
    else:
        sell_element = price_data[1]
        buy_element = price_data[0]

    # Debugging
    print(f"Sell Token Address: {sell_token_tocheck}")
    print(f"Sell Element: {sell_element}")
    print(f"Buy Element: {buy_element}")
    print("handle_trade_buy_token")

    # Extracting values for the sell token
    sell_symbol = sell_element['token']['symbol']
    sell_price = sell_element['priceUSD']
    sell_liquidity = sell_element['liquidity']
    sell_market_cap = sell_element['marketCap']
    sell_change1 = sell_element['change1']
    sell_change24 = sell_element['change24']

    # Extracting values for the buy token
    buy_symbol = buy_element['token']['symbol']
    buy_price = buy_element['priceUSD']
    buy_liquidity = buy_element['liquidity']
    buy_market_cap = buy_element['marketCap']
    buy_change1 = buy_element['change1']
    buy_change24 = buy_element['change24']

    trade_message = (
        f"💼 *Trade {buy_symbol}* - (Token) \n\n"
        f"📊 Balance: `{balance}` *{sell_symbol}* \n\n"
        f"💰 Price: *{format_number(buy_price)}* \\- LIQ: *{format_number(buy_liquidity)}* \\- MC: *{format_number(buy_market_cap)}*\n"
        # Use backticks for monospace formatting
    )

    if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
        keyboard = [
            [InlineKeyboardButton("↩️ Back", callback_data="trade_no")],
            [
                InlineKeyboardButton(f"25% {sell_symbol}",
                                     callback_data="25_amount"),
                InlineKeyboardButton(f"50% {sell_symbol}",
                                     callback_data="50_amount")
            ],
            [
                InlineKeyboardButton(f"75% {sell_symbol}",
                                     callback_data="75_amount"),
                InlineKeyboardButton(f"100% {sell_symbol}",
                                     callback_data="100_amount"),
            ],
            [
                InlineKeyboardButton(f"0.05 {sell_symbol}",
                                     callback_data="0.05_amount"),
                InlineKeyboardButton(f"0.1 {sell_symbol}",
                                     callback_data="0.1_amount")
            ],
            [
                InlineKeyboardButton(f"0.3 {sell_symbol}",
                                     callback_data="0.3_amount"),
                InlineKeyboardButton(f"0.5 {sell_symbol}",
                                     callback_data="0.5_amount"),
            ],
            [
                InlineKeyboardButton("X Slippage ✏️",
                                     callback_data="x_slippage"),
                InlineKeyboardButton(f"Amount X {sell_symbol} ✏️",
                                     callback_data="x_amount"),
            ],
            [
                InlineKeyboardButton("✅ 5% Slippage",
                                     callback_data="5_slippage"),
                InlineKeyboardButton("2% Slippage",
                                     callback_data="2_slippage"),
            ],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("↩️ Back", callback_data="trade_no")],
            [
                InlineKeyboardButton(f"25% {sell_symbol}",
                                     callback_data="25_amount"),
                InlineKeyboardButton(f"50% {sell_symbol}",
                                     callback_data="50_amount")
            ],
            [
                InlineKeyboardButton(f"75% {sell_symbol}",
                                     callback_data="75_amount"),
                InlineKeyboardButton(f"100% {sell_symbol}",
                                     callback_data="100_amount"),
            ],
            [
                InlineKeyboardButton("X Slippage ✏️",
                                     callback_data="x_slippage"),
                InlineKeyboardButton(f"Amount X {sell_symbol} ✏️",
                                     callback_data="x_amount"),
            ],
            [
                InlineKeyboardButton("✅ 5% Slippage",
                                     callback_data="5_slippage"),
                InlineKeyboardButton("2% Slippage",
                                     callback_data="2_slippage"),
            ],
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the message with MarkdownV2 parsing
    await update.message.reply_text(trade_message,
                                    parse_mode="Markdown",
                                    reply_markup=reply_markup)

    # await update.message.reply_text(
    #     f"How much {context.user_data['trade_sell_token']} would you like to trade?",
    #     reply_markup=ForceReply())


async def handle_trade_sell_token_auto(
        update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the buy token input."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    sell_token = update.message.text
    if not Web3.is_address(sell_token):
        await update.message.reply_text("Please provide a valid address.")
        return
    context.user_data['trade_sell_token'] = sell_token
    context.user_data['awaiting_trade_sell_token_auto'] = False
    context.user_data['slippage_for_trade'] = "5"
    # Create a Web3 instance using HTTPProvider
    w3 = Web3(
        Web3.HTTPProvider(
            'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
        ))

    # Convert the sell token from context to a checksum address
    buy_token_new = Web3.to_checksum_address(
        context.user_data['trade_buy_token'])
    buy_token = Web3.to_checksum_address(context.user_data['trade_buy_token'])

    # Convert the buy token from the user's message text to a checksum address
    sell_token = Web3.to_checksum_address(update.message.text)
    print(f"Buy token checksum address: {buy_token_new}")
    print(f"Buy token checksum address: {buy_token}")
    print(f"Sell token checksum address: {sell_token}")
    # Obtain the user's wallet, or create one if it doesn't exist
    wallet = await get_or_create_address(update)
    owner_address = wallet.address_id

    # Fetch and compute balance depending on the token type
    if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
        balance_wei = w3.eth.get_balance(
            Web3.to_checksum_address(
                owner_address))  # Use the owner's address for ETH balance
        balance = w3.from_wei(balance_wei, 'ether')

    # Convert balance from wei to ether
    else:
        balance = Decimal(wallet.balance(sell_token))  # Fetch token balance
    print(f"Balance: {balance}")

    chain = 8453
    tokens = [
        f"0x4200000000000000000000000000000000000006:{chain}"
        if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        else f"{Web3.to_checksum_address(sell_token)}:{chain}",
        f"0x4200000000000000000000000000000000000006:{chain}"
        if buy_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        else f"{Web3.to_checksum_address(buy_token)}:{chain}"
    ]

    price_data = fetch_price_from_codex(tokens, chain)

    sell_token_tocheck = "0x4200000000000000000000000000000000000006" if sell_token.lower(
    ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else sell_token

    if price_data[0]['token']['address'].lower() == sell_token_tocheck.lower():
        sell_element = price_data[0]
        buy_element = price_data[1]
    else:
        sell_element = price_data[1]
        buy_element = price_data[0]

    # Debugging
    print(f"Sell Token Address: {sell_token_tocheck}")
    print(f"Sell Element: {sell_element}")
    print(f"Buy Element: {buy_element}")
    print('handle_trade_sell_token_auto')

    # Extracting values for the sell token
    sell_symbol = sell_element['token']['symbol']
    sell_price = sell_element['priceUSD']
    sell_liquidity = sell_element['liquidity']
    sell_market_cap = sell_element['marketCap']
    sell_change1 = sell_element['change1']
    sell_change24 = sell_element['change24']

    # Extracting values for the buy token
    buy_symbol = buy_element['token']['symbol']
    buy_price = buy_element['priceUSD']
    buy_liquidity = buy_element['liquidity']
    buy_market_cap = buy_element['marketCap']
    buy_change1 = buy_element['change1']
    buy_change24 = buy_element['change24']

    trade_message = (
        f"💼 <b>Sell</b> \n\n"
        f"📊 Balance: <code>{balance}</code> <b>{sell_symbol}</b> \n\n"
        f"💰 Price: <b>{format_number(buy_price)}</b> - LIQ: <b>{format_number(buy_liquidity)}</b> - MC: <b>{format_number(buy_market_cap)}</b>\n"
    )
    print(trade_message)
    # Inline Keyboard Layout
    if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
        keyboard = [
            [InlineKeyboardButton("↩️ Back", callback_data="trade_no")],
            [
                InlineKeyboardButton(f"25% {sell_symbol}",
                                     callback_data="25_amount"),
                InlineKeyboardButton(f"50% {sell_symbol}",
                                     callback_data="50_amount")
            ],
            [
                InlineKeyboardButton(f"75% {sell_symbol}",
                                     callback_data="75_amount"),
                InlineKeyboardButton(f"100% {sell_symbol}",
                                     callback_data="100_amount"),
            ],
            [
                InlineKeyboardButton(f"0.05 {sell_symbol}",
                                     callback_data="0.05_amount"),
                InlineKeyboardButton(f"0.1 {sell_symbol}",
                                     callback_data="0.1_amount")
            ],
            [
                InlineKeyboardButton(f"0.3 {sell_symbol}",
                                     callback_data="0.3_amount"),
                InlineKeyboardButton(f"0.5 {sell_symbol}",
                                     callback_data="0.5_amount"),
            ],
            [
                InlineKeyboardButton("X Slippage ✏️",
                                     callback_data="x_slippage"),
                InlineKeyboardButton(f"Amount X {sell_symbol} ✏️",
                                     callback_data="x_amount"),
            ],
            [
                InlineKeyboardButton("✅ 5% Slippage",
                                     callback_data="5_slippage"),
                InlineKeyboardButton("2% Slippage",
                                     callback_data="2_slippage"),
            ],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("↩️ Back", callback_data="trade_no")],
            [
                InlineKeyboardButton(f"25% {sell_symbol}",
                                     callback_data="25_amount"),
                InlineKeyboardButton(f"50% {sell_symbol}",
                                     callback_data="50_amount")
            ],
            [
                InlineKeyboardButton(f"75% {sell_symbol}",
                                     callback_data="75_amount"),
                InlineKeyboardButton(f"100% {sell_symbol}",
                                     callback_data="100_amount"),
            ],
            [
                InlineKeyboardButton("X Slippage ✏️",
                                     callback_data="x_slippage"),
                InlineKeyboardButton(f"Amount X {sell_symbol} ✏️",
                                     callback_data="x_amount"),
            ],
            [
                InlineKeyboardButton("✅ 5% Slippage",
                                     callback_data="5_slippage"),
                InlineKeyboardButton("2% Slippage",
                                     callback_data="2_slippage"),
            ],
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    print("till here all ok")

    await message.reply_text(trade_message,
                             parse_mode="HTML",
                             reply_markup=reply_markup)


async def handle_trade_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle the trade amount input."""
    try:
        print(context.user_data['slippage_for_trade'],
              "context.user_data['slippage_for_trade'] ")
        w3 = Web3(
            Web3.HTTPProvider(
                'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
            ))
        amount = (context.user_data['amount_to_trade'])
        print(amount, "amount")
        sell_token = Web3.to_checksum_address(
            context.user_data['trade_sell_token'])
        buy_token = Web3.to_checksum_address(
            context.user_data['trade_buy_token'])

        wallet = await get_or_create_address(update)
        owner_address = wallet.address_id
        if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
            balance = w3.eth.get_balance(
                Web3.to_checksum_address(
                    owner_address))  # Fetch ETH balance# Fetch ETH balance
        else:
            balance = Decimal(wallet.balance(sell_token))
        print(balance)

        slippage = context.user_data[
            'slippage_for_trade'] if context.user_data.get(
                'slippage_for_trade') else "5"

        if (amount) <= 0:
            await update.message.reply_text("Please enter a positive amount.")
        elif amount > balance:
            await update.message.reply_text(
                f"Insufficient balance. Your current {sell_token} balance is {balance}."
            )
        else:
            chain = 8453
            tokens = [
                f"0x4200000000000000000000000000000000000006:{chain}"
                if sell_token.lower()
                == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else
                f"{Web3.to_checksum_address(sell_token)}:{chain}",
                f"0x4200000000000000000000000000000000000006:{chain}"
                if buy_token.lower()
                == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else
                f"{Web3.to_checksum_address(buy_token)}:{chain}"
            ]

            price_data = fetch_price_from_codex(tokens, chain)

            sell_token_tocheck = "0x4200000000000000000000000000000000000006" if sell_token.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else sell_token

            if price_data[0]['token']['address'].lower(
            ) == sell_token_tocheck.lower():
                sell_element = price_data[0]
                buy_element = price_data[1]
            else:
                sell_element = price_data[1]
                buy_element = price_data[0]

            # Debugging
            print(f"Sell Token Address: {sell_token_tocheck}")
            print(f"Sell Element: {sell_element}")
            print(f"Buy Element: {buy_element}")
            print("handle_trade_amount")

            # Extracting values for the sell token
            sell_symbol = sell_element['token']['symbol']
            sell_price = sell_element['priceUSD']
            sell_liquidity = sell_element['liquidity']
            sell_market_cap = sell_element['marketCap']
            sell_change1 = sell_element['change1']
            sell_change24 = sell_element['change24']

            # Extracting values for the buy token
            buy_symbol = buy_element['token']['symbol']
            buy_price = buy_element['priceUSD']
            buy_liquidity = buy_element['liquidity']
            buy_market_cap = buy_element['marketCap']
            buy_change1 = buy_element['change1']
            buy_change24 = buy_element['change24']

            # Print for verification
            print(f"Sell Symbol: {sell_symbol}, Buy Symbol: {buy_symbol}")

            print(
                f"First Token - Price: {sell_price}, Liquidity: {sell_liquidity}, Market Cap: {sell_market_cap}"
            )
            print(
                f"Second Token - Price: {buy_price}, Liquidity: {buy_liquidity}, Market Cap: {buy_market_cap}"
            )

            sell_token_address = Web3.to_checksum_address(sell_token)
            print(sell_token_address)

            erc20_contract = None
            # Create contract instance
            if sell_token_address.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                sell_token_decimals = 18  # Directly use token decimal 18
            else:
                erc20_contract = w3.eth.contract(address=sell_token_address,
                                                 abi=ERC20_ABI)
                # Call decimals function inside a try block
                sell_token_decimals = erc20_contract.functions.decimals().call(
                )
            print(sell_token_decimals)
            converted_amount = int(amount * (10**sell_token_decimals))
            # API Call parameters
            wallet = await get_or_create_address(update)
            private_key = wallet.key.key.hex()
            account = Account.from_key(private_key)
            nonce = w3.eth.get_transaction_count(account.address)
            # Check if approval already given
            if sell_token_address.lower(
            ) != "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                current_allowance = erc20_contract.functions.allowance(
                    owner_address,
                    "0xfDAc2748713906ede00D023AA3E0Cc893828D30B").call()
                if current_allowance >= converted_amount:
                    await update.message.reply_text(
                        "Approval already exists, no need for new approval.")
                else:
                    await update.message.reply_text(
                        "Processing token approval…")
                    approve_tx = erc20_contract.functions.approve(
                        "0xfDAc2748713906ede00D023AA3E0Cc893828D30B",
                        converted_amount
                    ).build_transaction({
                        'chainId':
                        8453,  # Adjust as necessary (1 for Ethereum mainnet)
                        'gas': 200000,  # Provide an adequate gas limit
                        'gasPrice':
                        w3.eth.gas_price,  # Fetch current gas price
                        'nonce': nonce,
                    })
                    # Sign the transaction
                    signed_approve_tx = w3.eth.account.sign_transaction(
                        approve_tx, private_key)
                    try:
                        tx_hash = w3.eth.send_raw_transaction(
                            signed_approve_tx.raw_transaction)
                        await update.message.reply_text(
                            f"Successfully approved! Transaction hash: {tx_hash.hex()}"
                        )
                    except Exception as e:
                        await update.message.reply_text(
                            f"Approval failed: {str(e)}")

            sell_token_address_to_check = sell_token.lower(
            ) if sell_token.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else sell_token
            buy_token_address_to_check = buy_token.lower() if buy_token.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else buy_token
            await update.message.reply_text("Fetching the quote…")
            print("one issue")
            params = {
                "slippage": str(slippage),
                "amount": str(converted_amount
                              ),  # The amount should be converted to string
                "tokenIn": sell_token_address_to_check,
                "tokenOut": buy_token_address_to_check,
                "sender": owner_address,
                "receiver": owner_address,
                "chainId": 8453,
                "skipSimulation": False,
            }
            # print(params)
            post_url = 'https://metasolvertest.velvetdao.xyz/best-quotes'

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(post_url, json=params)
                    response.raise_for_status()
                    # print(response.json())

                except Exception as e:
                    error_msg = f"Fail to fetch routes please retry {e}."
                    print(error_msg)
                    retry_keyboard = [[
                        InlineKeyboardButton(
                            "Retry", callback_data='trade_token_amount_click')
                    ]]
                    retry_reply_markup = InlineKeyboardMarkup(retry_keyboard)
                    await update.message.reply_text(
                        error_msg, reply_markup=retry_reply_markup)
                    return

                keyboard = [[
                    InlineKeyboardButton("Yes", callback_data='trade_yes'),
                    InlineKeyboardButton("No", callback_data='trade_no')
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # print(response.json())
                meta_quote = response.json()
                # print(meta_quote['quotes'][0])
                context.user_data['meta_quote'] = meta_quote['quotes'][0]
                context.user_data['buy_token_details'] = {
                    'token_address': buy_token.lower(),
                    'symbol': buy_symbol,
                    'price': buy_price,
                    'liquidity': buy_liquidity,
                    'market_cap': buy_market_cap,
                    'change1': buy_change1,
                    'change24': buy_change24
                }
                best_quote = meta_quote['quotes'][0]['amountOut']
                # print(best_quote)
                try:
                    # Convert address to checksum format
                    buy_token_address = Web3.to_checksum_address(buy_token)
                    # print(buy_token_address)
                    # Create contract instance

                    if buy_token_address.lower(
                    ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                        buy_token_decimals = 18
                    else:
                        erc20_contract = w3.eth.contract(
                            address=buy_token_address, abi=ERC20_ABI)
                        # Call decimals function inside a try
                        buy_token_decimals = erc20_contract.functions.decimals(
                        ).call()
                    normal_amount = Decimal(best_quote) / Decimal(
                        10**buy_token_decimals)
                    price_impact = round(
                        ((Decimal(buy_price) * Decimal(normal_amount)) /
                         (Decimal(sell_price) * Decimal(amount)) - 1) * 100, 2)
                    symbol = "+" if price_impact > 0 else "-"
                    formatted_price_impact = f"{symbol}{abs(price_impact)}%"
                    if price_impact > 0:
                        colored_price_impact = f"{formatted_price_impact}"
                    else:
                        colored_price_impact = f" {formatted_price_impact}"

                    buy_change1_symbol = "+" if float(buy_change1) > 0 else "-"
                    buy_change1_formatted_price_impact = f"{buy_change1_symbol}{abs(round(float(buy_change1),6)):.6f}%"

                    buy_change24_symbol = "+" if float(
                        buy_change24) > 0 else "-"

                    buy_change24_formatted_price_impact = f"{buy_change1_symbol}{abs(round(float(buy_change24),6)):.6f}%"

                    sell_change1_symbol = "+" if float(
                        sell_change1) > 0 else "-"
                    sell_change1_formatted_price_impact = f"{sell_change1_symbol}{abs(round(float(sell_change1),6)):.6f}%"

                    sell_change24_symbol = "+" if float(
                        sell_change24) > 0 else "-"

                    sell_change24_formatted_price_impact = f"{sell_change1_symbol}{abs(round(float(sell_change24),6)):.6f}%"

                    print(round(Decimal(sell_price) * Decimal(amount), 2),
                          Decimal(amount), Decimal(sell_price))
                    print(round(Decimal(buy_price) * Decimal(normal_amount)),
                          2)
                    await update.message.reply_text(
                        f"Details ${sell_symbol} — ${buy_symbol} 📈 · 🔍\n"
                        f"Token address: {sell_element['token']['address']}\n"
                        f"Balance: {balance} ({sell_symbol})\n"
                        f"Price: ${format_number(sell_price)} — LIQ: ${format_number(sell_liquidity)} — MC: ${format_number(sell_market_cap)}\n\n"
                        f"1h: {sell_change1_formatted_price_impact} — 24h: {sell_change24_formatted_price_impact}\n\n"
                        f"Token address: {buy_element['token']['address']}\n"
                        f"Price: ${format_number(buy_price)} — LIQ: ${ format_number(buy_liquidity)} — MC: ${format_number(buy_market_cap)}\n\n"
                        f"1h: {buy_change1_formatted_price_impact} — 24h: {buy_change24_formatted_price_impact}\n\n"
                        # f"Renounced ✅\n\n"
                        f"🟢 Fetched Quote (Velvet)\n"
                        f"(${round(Decimal(sell_price) * Decimal(amount), 2)}) ↔️ "
                        f" (${round(Decimal(buy_price) * Decimal(normal_amount), 2)})\n\n"
                        f"Price Impact:{colored_price_impact}",
                        reply_markup=reply_markup,
                        parse_mode="HTML")
                    # context.user_data['awaiting_trade_confirmation'] = True
                except Exception as e:
                    await update.message.reply_text(
                        f"An error occurred when processing the token amount: {str(e)}"
                    )
        # Clear trade data
        context.user_data['awaiting_trade_amount'] = False
        context.user_data.pop('trade_sell_token', None)
        context.user_data.pop('trade_buy_token', None)
    except ValueError:
        await update.message.reply_text(
            "Invalid amount. Please enter a valid number.")


async def handle_trade_amount_click(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: CallbackQuery,
) -> None:
    """Handle the trade amount input."""
    message = update.callback_query.message if update.callback_query else update.message

    if not message:
        return
    try:
        w3 = Web3(
            Web3.HTTPProvider(
                'https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base'
            ))
        amount = (context.user_data['amount_to_trade'])
        print(amount, "amount")
        sell_token = Web3.to_checksum_address(
            context.user_data['trade_sell_token'])
        buy_token = Web3.to_checksum_address(
            context.user_data['trade_buy_token'])

        wallet = await get_or_create_address(update)
        owner_address = wallet.address_id
        if sell_token.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
            balance = w3.eth.get_balance(
                Web3.to_checksum_address(
                    owner_address))  # Fetch ETH balance# Fetch ETH balance
        else:
            balance = Decimal(wallet.balance(sell_token))
        print(balance, amount)

        slippage = context.user_data[
            'slippage_for_trade'] if context.user_data.get(
                'slippage_for_trade') else "5"

        if (amount) <= 0:
            await message.reply_text("Please enter a positive amount.")
        elif amount > balance:
            await message.reply_text(
                f"Insufficient balance. Your current {sell_token} balance is {balance}."
            )
        else:
            chain = 8453
            tokens = [
                f"0x4200000000000000000000000000000000000006:{chain}"
                if sell_token.lower()
                == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else
                f"{Web3.to_checksum_address(sell_token)}:{chain}",
                f"0x4200000000000000000000000000000000000006:{chain}"
                if buy_token.lower()
                == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else
                f"{Web3.to_checksum_address(buy_token)}:{chain}"
            ]

            price_data = fetch_price_from_codex(tokens, chain)

            sell_token_tocheck = "0x4200000000000000000000000000000000000006" if sell_token.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else sell_token

            if price_data[0]['token']['address'].lower(
            ) == sell_token_tocheck.lower():
                sell_element = price_data[0]
                buy_element = price_data[1]
            else:
                sell_element = price_data[1]
                buy_element = price_data[0]

            # Debugging
            print(f"Sell Token Address: {sell_token_tocheck}")
            print(f"Sell Element: {sell_element}")
            print(f"Buy Element: {buy_element}")
            print("handle_trade_amount_click")

            # Extracting values for the sell token
            sell_symbol = sell_element['token']['symbol']
            sell_price = sell_element['priceUSD']
            sell_liquidity = sell_element['liquidity']
            sell_market_cap = sell_element['marketCap']
            sell_change1 = sell_element['change1']
            sell_change24 = sell_element['change24']

            # Extracting values for the buy token
            buy_symbol = buy_element['token']['symbol']
            buy_price = buy_element['priceUSD']
            buy_liquidity = buy_element['liquidity']
            buy_market_cap = buy_element['marketCap']
            buy_change1 = buy_element['change1']
            buy_change24 = buy_element['change24']

            # Print for verification
            print(f"Sell Symbol: {sell_symbol}, Buy Symbol: {buy_symbol}")

            print(
                f"First Token - Price: {sell_price}, Liquidity: {sell_liquidity}, Market Cap: {sell_market_cap}"
            )
            print(
                f"Second Token - Price: {buy_price}, Liquidity: {buy_liquidity}, Market Cap: {buy_market_cap}"
            )

            sell_token_address = Web3.to_checksum_address(sell_token)
            print(sell_token_address)

            erc20_contract = None
            # Create contract instance
            if sell_token_address.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                sell_token_decimals = 18  # Directly use token decimal 18
            else:
                erc20_contract = w3.eth.contract(address=sell_token_address,
                                                 abi=ERC20_ABI)
                # Call decimals function inside a try block
                sell_token_decimals = erc20_contract.functions.decimals().call(
                )
            print(sell_token_decimals)
            converted_amount = int(amount * (10**sell_token_decimals))
            # API Call parameters
            wallet = await get_or_create_address(update)
            private_key = wallet.key.key.hex()
            account = Account.from_key(private_key)
            nonce = w3.eth.get_transaction_count(account.address)
            # Check if approval already given
            if sell_token_address.lower(
            ) != "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                current_allowance = erc20_contract.functions.allowance(
                    owner_address,
                    "0xfDAc2748713906ede00D023AA3E0Cc893828D30B").call()
                if current_allowance >= converted_amount:
                    await message.reply_text(
                        "Approval already exists, no need for new approval.")
                else:
                    await message.reply_text("Processing token approval…")

                    approve_tx = erc20_contract.functions.approve(
                        "0xfDAc2748713906ede00D023AA3E0Cc893828D30B",
                        converted_amount
                    ).build_transaction({
                        'chainId':
                        8453,  # Adjust as necessary (1 for Ethereum mainnet)
                        'gas': 200000,  # Provide an adequate gas limit
                        'gasPrice':
                        w3.eth.gas_price,  # Fetch current gas price
                        'nonce': nonce,
                    })
                    # Sign the transaction
                    signed_approve_tx = w3.eth.account.sign_transaction(
                        approve_tx, private_key)
                    try:
                        tx_hash = w3.eth.send_raw_transaction(
                            signed_approve_tx.raw_transaction)
                        await message.reply_text(
                            f"Successfully approved! Transaction hash: {tx_hash.hex()}"
                        )
                    except Exception as e:
                        await message.reply_text(f"Approval failed: {str(e)}")

            sell_token_address_to_check = sell_token.lower(
            ) if sell_token.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else sell_token
            buy_token_address_to_check = buy_token.lower() if buy_token.lower(
            ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else buy_token
            params = {
                "slippage": str(slippage),
                "amount": str(converted_amount
                              ),  # The amount should be converted to string
                "tokenIn": sell_token_address_to_check,
                "tokenOut": buy_token_address_to_check,
                "sender": owner_address,
                "receiver": owner_address,
                "chainId": 8453,
                "skipSimulation": False,
            }
            print(params)
            post_url = 'https://metasolvertest.velvetdao.xyz/best-quotes'
            await message.reply_text("Fetching the quote…")
            print("Two issue")
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(post_url, json=params)
                    response.raise_for_status()
                    # print(response.json())

                except Exception as e:
                    error_msg = f"Fail to fetch routes please retry {e}."
                    print(error_msg)
                    retry_keyboard = [[
                        InlineKeyboardButton(
                            "Retry", callback_data='trade_token_amount_click')
                    ]]
                    retry_reply_markup = InlineKeyboardMarkup(retry_keyboard)
                    await message.reply_text(error_msg,
                                             reply_markup=retry_reply_markup)
                    return

                keyboard = [[
                    InlineKeyboardButton("Yes", callback_data='trade_yes'),
                    InlineKeyboardButton("No", callback_data='trade_no')
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # print(response.json())
                meta_quote = response.json()
                # print(meta_quote['quotes'][0])
                context.user_data['meta_quote'] = meta_quote['quotes'][0]
                context.user_data['buy_token_details'] = {
                    'token_address': buy_token.lower(),
                    'symbol': buy_symbol,
                    'price': buy_price,
                    'liquidity': buy_liquidity,
                    'market_cap': buy_market_cap,
                    'change1': buy_change1,
                    'change24': buy_change24
                }
                best_quote = meta_quote['quotes'][0]['amountOut']
                # print(best_quote)
                try:
                    # Convert address to checksum format
                    buy_token_address = Web3.to_checksum_address(buy_token)
                    print(buy_token_address)
                    # Create contract instance

                    if buy_token_address.lower(
                    ) == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                        buy_token_decimals = 18
                    else:
                        erc20_contract = w3.eth.contract(
                            address=buy_token_address, abi=ERC20_ABI)
                        # Call decimals function inside a try
                        buy_token_decimals = erc20_contract.functions.decimals(
                        ).call()

                    print(buy_token_decimals)
                    normal_amount = Decimal(best_quote) / Decimal(
                        10**buy_token_decimals)

                    price_impact = round(
                        ((Decimal(buy_price) * Decimal(normal_amount)) /
                         (Decimal(sell_price) * Decimal(amount)) - 1) * 100, 2)
                    symbol = "+" if price_impact > 0 else "-"
                    formatted_price_impact = f"{symbol}{abs(price_impact)}%"
                    if price_impact > 0:
                        colored_price_impact = f" {formatted_price_impact}"
                    else:
                        colored_price_impact = f" {formatted_price_impact}"
                    buy_change1_symbol = "+" if float(buy_change1) > 0 else "-"
                    buy_change1_formatted_price_impact = f"{buy_change1_symbol}{abs(round(float(buy_change1),6)):.6f}%"

                    buy_change24_symbol = "+" if float(
                        buy_change24) > 0 else "-"

                    buy_change24_formatted_price_impact = f"{buy_change1_symbol}{abs(round(float(buy_change24),6)):.6f}%"

                    sell_change1_symbol = "+" if float(
                        sell_change1) > 0 else "-"
                    sell_change1_formatted_price_impact = f"{sell_change1_symbol}{abs(round(float(sell_change1),6)):.6f}%"

                    sell_change24_symbol = "+" if float(
                        sell_change24) > 0 else "-"

                    sell_change24_formatted_price_impact = f"{sell_change1_symbol}{abs(round(float(sell_change24),6)):.6f}%"

                    await message.reply_text(
                        f"Details ${sell_symbol} — ${buy_symbol} 📈 · 🔍\n"
                        f"Token address: {sell_element['token']['address']}\n"
                        f"Balance: {balance} ({sell_symbol})\n"
                        f"Price: ${format_number(sell_price)} — LIQ: ${format_number(sell_liquidity)} — MC: ${format_number(sell_market_cap)}\n\n"
                        f"1h: {sell_change1_formatted_price_impact} — 24h: {sell_change24_formatted_price_impact}\n\n"
                        f"Token address: {buy_element['token']['address']}\n"
                        f"Price: ${format_number(buy_price)} — LIQ: ${ format_number(buy_liquidity)} — MC: ${format_number(buy_market_cap)}\n\n"
                        f"1h: {buy_change1_formatted_price_impact} — 24h: {buy_change24_formatted_price_impact}\n\n"
                        # f"Renounced ✅\n\n"
                        f"🟢 Fetched Quote (Velvet)\n"
                        f"(${round(Decimal(sell_price) * Decimal(amount), 2)}) ↔️ "
                        f" (${round(Decimal(buy_price) * Decimal(normal_amount), 2)})\n\n"
                        f"Price Impact:{colored_price_impact}",
                        reply_markup=reply_markup,
                        parse_mode="HTML")
                    # context.user_data['awaiting_trade_confirmation'] = True
                except Exception as e:
                    await message.reply_text(
                        f"An error occurred when processing the token amount: {str(e)}"
                    )
        # Clear trade data
        context.user_data['awaiting_trade_amount'] = False
        context.user_data.pop('trade_sell_token', None)
        context.user_data.pop('trade_buy_token', None)
    except ValueError:
        await message.reply_text("Invalid amount. Please enter a valid number."
                                 )


async def handle_trade_yes(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger handling trade confirmation when user clicks 'yes'."""
    print("inside handle_trade_yes")
    # Call the handle_trade_confirmation function directly on confirmation
    # await handle_trade_confirmation(update, context)


async def handle_trade_confirmation(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE,
                                    query: CallbackQuery) -> None:
    """Handle the trade confirmation response and access meta_quote."""
    # query = update
    meta_quote = context.user_data.get('meta_quote', {})
    buy_token_details = context.user_data.get('buy_token_details', {})
    print(buy_token_details)
    # await query.answer()
    await query.message.reply_text("Executing the transaction…")
    # print(update)
    try:
        wallet = await get_or_create_address(update)
        private_key = wallet.key.key.hex()
        provider_url = "https://open-platform.nodereal.io/3b8deb40026a4db88288217f675a5165/base"
        w3 = Web3(Web3.HTTPProvider(provider_url))
        account = Account.from_key(private_key)
        gas_price = w3.eth.gas_price
        print(gas_price)
        tx_data = {
            "to":
            meta_quote['to'],
            "data":
            meta_quote['data'],
            "value":
            int(meta_quote['value']),
            "gas": (int(meta_quote['gasEstimate'] *
                        2) if meta_quote['gasEstimate'] != 0 else 18000000),
            "gasPrice":
            int(gas_price),
            "nonce":
            w3.eth.get_transaction_count(account.address),
            "from":
            account.address,
            "chainId":
            8453,
        }
        # print(tx_data)

        # Sign the transaction with the private key
        signed_tx = w3.eth.account.sign_transaction(tx_data, private_key)

        # Define the API URL
        url = "https://tbotserver.velvetdao.xyz/add-token"

        # Payload for the POST request
        payload = {
            "walletAddress": account.address.lower(),
            "tokenName": buy_token_details["symbol"],
            "tokenAddress": buy_token_details["token_address"],
            "tokenAmount": buy_token_details["price"]
        }

        print("payload for request", payload)
        # Headers for the POST request
        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "69420"
        }

        # Wait for the transaction receipt (confirm the transaction)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transaction Hash: {tx_hash.hex()}")
        # Make the POST request
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status(
            )  # Raise an HTTPError for bad responses (4xx and 5xx)
            print("Response:", response.json())
        except requests.exceptions.RequestException as e:
            print("Transaction completed fail to store token details for PnL:",
                  e)

        context.user_data['meta_quote'] = {}
        context.user_data['buy_token_details'] = {}
        await query.message.reply_text(
            f"Transaction completed with hash: \n"
            f"https://basescan.org/tx/0x{tx_hash.hex()}")
    except Exception as e:
        error_message = str(e)
        print(error_message)
        await query.message.reply_text(
            f"An error occurred during the trade: {error_message}")
    context.user_data['awaiting_trade_confirmation'] = False


async def handle_message(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('awaiting_withdraw_amount'):
        await handle_withdraw_amount(update, context)
    elif context.user_data.get('awaiting_withdraw_address'):
        await handle_withdraw_address(update, context)
    elif context.user_data.get('awaiting_trade_confirmation'):
        await handle_trade_confirmation(update, context, query)
    elif context.user_data.get('awaiting_buy_amount'):
        await handle_buy_amount(update, context)
    elif context.user_data.get('awaiting_x_amount'):
        await handling_x_amount(update, context)
    elif context.user_data.get('awaiting_buy_asset'):
        await handle_buy_asset(update, context)
    elif context.user_data.get('awaiting_sell_asset'):
        await handle_sell_asset(update, context)
    elif context.user_data.get('awaiting_trade_sell_token'):
        await handle_trade_sell_token(update, context)
    elif context.user_data.get('awaiting_trade_sell_token_auto'):
        await handle_trade_sell_token_auto(update, context)
    elif context.user_data.get('awaiting_sell_amount'):
        await handle_sell_amount(update, context)
    elif context.user_data.get('awaiting_trade_buy_token'):
        await handle_trade_buy_token(update, context)
    elif context.user_data.get('awaiting_trade_amount'):
        await handle_trade_amount(update, context)


from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64


def encrypt(data: dict, iv: str) -> str:
    """
    Encrypts the given data using AES-256 encryption.

    :param data: Dictionary containing the data to be encrypted
    :param iv: Initialization vector as a string
    :return: Encrypted data as a base64 encoded string
    """
    global encryption_key
    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")

    key = bytes.fromhex(encryption_key)

    iv = bytes.fromhex(iv)

    json_data = json.dumps(data)

    cipher = AES.new(key, AES.MODE_CBC, iv)

    padded_data = pad(json_data.encode('utf-8'), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)

    result = base64.b64encode(encrypted_data).decode('utf-8')
    return result


def decrypt(encrypted_data: str, iv: str) -> dict:
    """
    Decrypts the given encrypted data using AES-256 decryption.

    :param encrypted_data: Base64 encoded encrypted data as a string
    :param iv: Initialization vector as a string
    :return: Decrypted data as a dictionary
    """
    global encryption_key
    if not encryption_key:
        logger.error("ENCRYPTION_KEY environment variable is not set")
        raise ValueError("ENCRYPTION_KEY environment variable is not set")

    key = bytes.fromhex(encryption_key)

    iv = bytes.fromhex(iv)

    encrypted_data = base64.b64decode(encrypted_data)

    cipher = AES.new(key, AES.MODE_CBC, iv)

    decrypted_data = cipher.decrypt(encrypted_data)

    unpadded_data = unpad(decrypted_data, AES.block_size)

    result = json.loads(unpadded_data.decode('utf-8'))
    return result


def main() -> None:
    """Start the bot."""
    # Initialize the CDP SDK
    Cdp.configure(cdp_api_key_name, cdp_api_key_private_key)

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(telegram_bot_token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", handle_trade_token_sell))
    application.add_handler(CommandHandler("sell", handle_trade_token_buy))

    application.add_handler(
        CommandHandler("balance", handle_button_check_balance))
    application.add_handler(CommandHandler("trade", handle_button_trade))
    application.add_handler(CommandHandler("positions", handle_my_position))
    application.add_handler(
        CommandHandler("deposit", handle_button_deposit_eth))
    application.add_handler(
        CommandHandler("withdraw", handle_button_withdraw_eth))
    application.add_handler(CommandHandler("referral", handle_button_referral))
    application.add_handler(CommandHandler("export", handle_button_export_key))

    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    # try:
    #     loop = asyncio.get_running_loop()
    # except RuntimeError:
    #     loop = None

    # if loop and loop.is_running():
    #     print(
    #         "Event loop already running, running the bot in the current loop.")
    #     asyncio.ensure_future(main())
    # else:
    #     asyncio.run(main())