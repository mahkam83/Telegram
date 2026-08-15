import os
import datetime
import pandas as pd
from dotenv import load_workbook, load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

load_dotenv()

# --- Configuration Constants (EDIT THESE) ---
# Replace 'YOUR_BOT_TOKEN_HERE' with your actual Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN") 
if not BOT_TOKEN:
    raise ValueError("Error: Bot Token ENVM is missing!")

# The name of the Excel file where data will be stored
EXCEL_FILE = "collected_field_data.xlsx"

# Conversation States
REQUEST_PHONE, REQUEST_LOCATION, REQUEST_SITE_CODE, REQUEST_TCR_NUMBER = range(4)


# --- Helper Function for Data Storage ---

def save_to_excel(data: dict):
    """
    Appends the collected data (a dictionary) to the specified Excel file.
    Creates the file if it doesn't exist.
    """
    try:
        # Create a new DataFrame from the single data entry
        new_df = pd.DataFrame([data])

        if os.path.exists(EXCEL_FILE):
            # Read the existing data
            existing_df = pd.read_excel(EXCEL_FILE)
            # Combine the existing data with the new entry
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            # If the file doesn't exist, the new DataFrame is the updated one
            updated_df = new_df

        # Save the updated DataFrame back to the Excel file
        updated_df.to_excel(EXCEL_FILE, index=False)
        print(f"Data saved successfully to {EXCEL_FILE}")
        return True
    except Exception as e:
        print(f"Error saving data to Excel: {e}")
        return False


# --- Conversation Handler Functions ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a welcome message and asks for the user's contact number via button."""
    
    # 1. Create a button that specifically requests the user's phone number
    keyboard = [
        [KeyboardButton("Share Contact Number", request_contact=True)],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Welcome! To begin, please share your contact number using the 'Share Contact Number' button below.",
        reply_markup=reply_markup
    )
    
    # Move to the next state: waiting for the phone number
    return REQUEST_PHONE

async def request_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the contact, stores it, and asks for the GPS location via manual instruction."""
    
    if not update.message.contact:
        await update.message.reply_text("I need your contact number via the button. Please try again or type /cancel.")
        return REQUEST_PHONE

    contact_number = update.message.contact.phone_number
    
    # Store the contact number in the conversation context
    context.user_data['contact_number'] = contact_number

    # 2. Instruct the user to manually share their Live Location.
    # The dedicated button is removed as it cannot trigger Live Location.
    await update.message.reply_text(
        f"Thank you, {contact_number}. The next step requires a **Live Location**.\n\n"
        "**CRITICAL:** Please use the attachment (📎) icon in the chat and select:\n"
        "**Location → Share Live Location** for only 15 minutes.\n"
        , parse_mode='Markdown'
        , reply_markup=ReplyKeyboardRemove() # Remove keyboard after contact is shared
    )
    
    # Move to the next state: waiting for the location (which comes as a LOCATION object)
    return REQUEST_LOCATION

async def request_site_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the location, stores coordinates, and asks for the site code."""
    
    # 1. Check if a location was received at all
    if not update.message.location:
        await update.message.reply_text("I need your GPS location. Please try again or type /cancel.")
        return REQUEST_LOCATION

    # 2. CRITICAL CHECK: Ensure it is a Live Location by checking for live_period
    # A Live Location message will have a live_period (integer in seconds) set.
    # A static/current location message will have live_period as None.
    if not update.message.location.live_period:
        await update.message.reply_text(
            "⚠️ **Invalid Location Type.** You must share your **Live Location**, not a static/current location. "
            "Please use the attachment icon (📎) and choose **Share Live Location**."
            , parse_mode='Markdown'
        )
        # Stay in the current state to force the user to share the correct type of location
        return REQUEST_LOCATION 

    latitude = update.message.location.latitude
    longitude = update.message.location.longitude

    # Store the location in the conversation context
    context.user_data['latitude'] = latitude
    context.user_data['longitude'] = longitude

    await update.message.reply_text(
        f"Live Location accepted (Lat: {latitude:.4f}, Lon: {longitude:.4f}).\n\nPlease enter the Site Code now.",
        reply_markup=ReplyKeyboardRemove() # Ensure no keyboard is present for text input
    )
    
    # Move to the next state: waiting for the site code
    return REQUEST_SITE_CODE

async def request_tcr_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the Site Code, stores it, and asks for the TCR number."""
    
    site_code = update.message.text.strip()
    
    if not site_code:
        await update.message.reply_text("The Site Code cannot be empty. Please enter the Site Code.")
        return REQUEST_SITE_CODE

    # Store the site code in the conversation context
    context.user_data['site_code'] = site_code

    await update.message.reply_text(
        f"Site Code '{site_code}' recorded. Finally, please enter the TCR number."
    )
    
    # Move to the next state: waiting for the TCR number
    return REQUEST_TCR_NUMBER

async def finish_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the TCR number, stores all data, saves to Excel, and ends conversation."""
    
    tcr_number = update.message.text.strip()

    if not tcr_number:
        await update.message.reply_text("The TCR Number cannot be empty. Please enter the TCR number.")
        return REQUEST_TCR_NUMBER

    # Store the final piece of data
    context.user_data['tcr_number'] = tcr_number
    
    # Compile all data
    final_data = {
        "Contact Number": context.user_data.get('contact_number'),
        "Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Site Code": context.user_data.get('site_code'),
        "TCR Number": context.user_data.get('tcr_number'),
        "Latitude": context.user_data.get('latitude'),
        "Longitude": context.user_data.get('longitude'),
    }

    # Save to Excel
    if save_to_excel(final_data):
        await update.message.reply_text(
            "✅ Data saved successfully!\n\n"
            f"Summary:\n"
            f"Contact: {final_data['Contact Number']}\n"
            f"Site Code: {final_data['Site Code']}\n"
            f"TCR Number: {final_data['TCR Number']}\n"
            f"Coordinates: ({final_data['Latitude']:.4f}, {final_data['Longitude']:.4f})\n\n"
            "Type /start to begin a new entry."
        )
    else:
        await update.message.reply_text(
            "⚠️ Data collection failed due to a file saving error. Please check the console log for details. Type /start to try again."
        )

    # Clear user data and end the conversation
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allows the user to cancel the operation at any time."""
    await update.message.reply_text(
        "Operation cancelled. You can start a new entry with /start.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def generic_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles generic text input when expecting contact/location buttons."""
    # Note: We need to figure out which state we are in to give specific advice
    current_state = context.user_data.get('current_state') 
    
    # The actual state is stored by the ConversationHandler, not context.user_data,
    # so we rely on the state-specific MessageHandlers to filter correctly.
    # The generic_fallback function is used only in the first two states for non-button inputs.

    if update.message.contact:
         message = "You have already shared your contact number. Please share your Live Location now as instructed."
    elif update.message.location:
         message = "You have already shared your location. Please proceed by typing the Site Code."
    elif update.message.text and update.message.text.lower() in ['share contact number', 'share gps location']:
         message = "Please use the official Telegram sharing mechanism via the provided buttons or the attachment menu, do not type the button text."
    else:
         # Default message for when expecting a specific file type (Contact or Location)
         message = "I am currently waiting for your shared Contact Number or Live Location. Please follow the previous instruction."
        
    await update.message.reply_text(message)


# --- Main Application Setup ---

def main() -> None:
    """Starts the bot."""
    
    print("Starting bot...")
    
    # 1. Create the Application and pass your bot's token
    application = Application.builder().token(BOT_TOKEN).build()

    # 2. Define the ConversationHandler
    # This handler manages the multi-step form process
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        
        states={
            # State 1: Waiting for Contact Button
            REQUEST_PHONE: [
                # Only accepts messages that contain a Contact object (i.e., button share)
                MessageHandler(filters.CONTACT & ~filters.COMMAND, request_location),
                # Fallback for plain text input
                MessageHandler(filters.TEXT & ~filters.COMMAND, generic_fallback),
            ],
            
            # State 2: Waiting for manual Location share (Live Location)
            REQUEST_LOCATION: [
                # Only accepts messages that contain a Location object (from either static or live share)
                MessageHandler(filters.LOCATION & ~filters.COMMAND, request_site_code),
                # Fallback for plain text input
                MessageHandler(filters.TEXT & ~filters.COMMAND, generic_fallback),
            ],
            
            # State 3: Waiting for Site Code text input
            REQUEST_SITE_CODE: [
                # Accepts any text input
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_tcr_number),
            ],
            
            # State 4: Waiting for TCR Number text input (Final step)
            REQUEST_TCR_NUMBER: [
                # Accepts any text input and finishes
                MessageHandler(filters.TEXT & ~filters.COMMAND, finish_and_save),
            ],
        },
        
        # Allows user to cancel the conversation flow
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add the conversation handler to the application
    application.add_handler(conv_handler)
    
    # Add a simple /help command
    application.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text(
        "Use /start to begin the data collection. Use /cancel to stop at any time."
    )))

    # 3. Run the bot until the user presses Ctrl-C
    print("Bot is running. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()