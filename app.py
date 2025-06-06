import streamlit as st
import requests
import json
import pandas as pd
import pdfplumber
import io
import logging
from datetime import datetime
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output to terminal
        logging.FileHandler(f'ddc_ai_assistant_{datetime.now().strftime("%Y%m%d")}.log')  # Output to daily log file
    ]
)
logger = logging.getLogger(__name__)

# Page Configuration - MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="DDC Foods AI Assistant", # Uses YOUR_SITE_NAME
    page_icon="🛒", # Generic store/cart icon
    layout="centered"
)

# Configuration
OPENROUTER_API_KEY = "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"
YOUR_SITE_URL = "https://www.ddcfoods.co.uk"
YOUR_SITE_NAME = "DDC Foods AI Assistant"
MODEL_NAME = "deepseek/deepseek-chat-v3-0324:free"

SYSTEM_PROMPT = """✅ SYSTEM PROMPT – DDC FOODS AI ASSISTANT

You are an AI assistant representing DDC Foods Ltd, a UK-based food and drink distributor. You are used internally by staff and externally on the website. Your knowledge reflects the company's operations, values, and product catalogue as of 2025.

⸻

COMPANY PROFILE
	•	Name: DDC Foods Ltd
	•	Founded: 1996
	•	Location: Maylands House, Maylands Avenue, Hemel Hempstead, Hertfordshire, HP2 7DE, United Kingdom
	•	Website: www.ddcfoods.co.uk
	•	Next-Day Delivery: Available inside M25 for weekday orders placed before 12pm


⸻

PRODUCT CATEGORIES & FEATURES

DDC offers a wide range of branded and alternative snacks, drinks, and health products, distributed in both retail and wholesale formats.

1. Crisps & Snacks
	•	Brands: Walkers, Kettle, Tyrrells, Hippeas, Popchips, Two Farmers, Properchips, Pringles, etc.
	•	Attributes: Includes gluten-free, vegan, halal, kosher, low-sugar options.
	•	Formats: Single serve to bulk packs.

2. Fruits, Nuts & Seeds
	•	Brands: Forest Feast, Urban Fruit, Bear Snacks, Boundless, Deliciously Ella.
	•	Attributes: Vegan, vegetarian, gluten-free, kosher, high-fibre.
	•	Pack sizes: From 30g to 1kg bulk.

3. Health & Wellness Bars
	•	Brands: KIND, Tribe, RESQ, The Protein Ball Co, Nick's.
	•	Attributes: Protein-rich, vegan, low sugar, multivitamin-enhanced.

4. Dairy & Alternatives
	•	Primary Brand: The Collective.
	•	Attributes: Dairy and plant-based yoghurt, allergen-free ranges.

5. Soft Drinks & Hydration
	•	Brands: Get More Vits, Zooki, Soul Fruit.
	•	Features: Enriched with vitamins and minerals, suitable for health-conscious consumers.

⸻

📦 ALLERGENS & DIETARY LABELS
Key categories: Vegetarian, Vegan, Gluten-free, Dairy-free, Nut-free, Kosher, Halal. All products comply with UK food labelling regulations.

⸻

🤖 USAGE INSTRUCTIONS

Internal (Staff):
• Order lookup, stock levels, product attributes
• Sales recommendations and allergen data
• Brand partnership alternatives

External (Public):
• Product queries and dietary filtering
• Professional tone aligned with DDC Foods
• M25 next-day delivery info (orders before noon)

⸻

🔗 REFERENCES
• www.ddcfoods.co.uk
• DDC Product Pages
• Brand pages (e.g., KIND, The Collective)
"""

# Streamlit app title
st.title(YOUR_SITE_NAME)

# Initialize OpenAI client with OpenRouter configuration
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "user" and "image_bytes_for_display" in message:
                st.image(
                    message["image_bytes_for_display"],
                    caption=f"Uploaded: {message.get('image_name_for_display', 'Image')}",
                    width=300
                )

# Chat input and file upload form
with st.form(key="chat_form"):
    user_text_prompt = st.text_input("Your message:", key="user_prompt_text_key")
    uploaded_file = st.file_uploader( # Merged file uploader
        "Upload File (Excel, PDF, or Image, optional)",
        type=["xlsx", "xls", "pdf", "png", "jpg", "jpeg"],
        key="file_uploader_key" # New key for the merged uploader
    )
    submit_button = st.form_submit_button(label="Send / Process Files")

if submit_button:
    logger.info("Form submitted - Processing user input and files")
    # Updated condition to check the single uploaded_file
    if not user_text_prompt.strip() and not uploaded_file:
        logger.warning("No input provided - neither message nor file")
        st.warning("Please enter a message or upload a file.")
        st.stop()

    user_api_content_parts = []
    user_display_message_parts = []

    if user_text_prompt.strip():
        logger.info(f"Processing text prompt: {user_text_prompt}")
        user_api_content_parts.append({"type": "text", "text": user_text_prompt})
        user_display_message_parts.append(user_text_prompt)

    # Consolidated file processing logic for the single uploader
    processed_image_file_bytes = None
    processed_image_file_name = None
    # file_type is already declared and used below, will help identify if image was processed
    
    if uploaded_file:
        file_name = uploaded_file.name
        logger.info(f"Processing uploaded file: {file_name}")
        file_bytes = uploaded_file.getvalue()
        
        processed_this_file = False
        file_type = None # To determine if it's an image for later display

        if file_name.lower().endswith((".xlsx", ".xls")):
            try:
                logger.info(f"Processing Excel file: {file_name}")
                df = pd.read_excel(io.BytesIO(file_bytes))
                excel_json = df.to_json(orient="records", indent=2)
                file_content_for_api = f"--- Content from Excel file: {file_name} ---\n{excel_json}"
                user_api_content_parts.append({"type": "text", "text": file_content_for_api})
                user_display_message_parts.append(f"(Attached Excel: {file_name})")
                processed_this_file = True
                file_type = "excel"
                logger.info(f"Successfully processed Excel file: {file_name}")
            except Exception as e:
                logger.error(f"Error processing Excel file {file_name}: {str(e)}")
                st.error(f"Error processing Excel file {file_name}: {e}")
                user_display_message_parts.append(f"(Failed to process Excel: {file_name})")

        elif file_name.lower().endswith(".pdf"):
            try:
                logger.info(f"Processing PDF file: {file_name}")
                pdf_text_parts = []
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        logger.info(f"Processing PDF page {page_num + 1}")
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            pdf_text_parts.append(f"--- Page {page_num + 1} of {file_name} ---\n{page_text.strip()}")
                
                if not pdf_text_parts:
                    logger.warning(f"No text extracted from PDF file: {file_name}")
                    file_content_for_api = f"--- No text could be extracted from PDF file: {file_name} ---"
                else:
                    file_content_for_api = (
                        f"--- Content from PDF file: {file_name} ---\n"
                        + "\n\n".join(pdf_text_parts)
                    )
                
                user_api_content_parts.append({"type": "text", "text": file_content_for_api})
                user_display_message_parts.append(f"(Attached PDF: {file_name})")
                processed_this_file = True
                file_type = "pdf"
                logger.info(f"Successfully processed PDF file: {file_name}")
            except Exception as e:
                logger.error(f"Error processing PDF file {file_name}: {str(e)}")
                st.error(f"Error processing PDF file {file_name}: {e}")
                user_display_message_parts.append(f"(Failed to process PDF: {file_name})")
        
        elif file_name.lower().endswith((".png", ".jpg", ".jpeg")):
            import base64
            try:
                logger.info(f"Processing image file: {file_name}")
                base64_image = base64.b64encode(file_bytes).decode('utf-8')
                mime_type = f"image/{file_name.split('.')[-1].lower()}"
                if mime_type == "image/jpg": mime_type = "image/jpeg" # Common practice
                
                data_url = f"data:{mime_type};base64,{base64_image}"
                
                user_api_content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_url}
                })
                user_display_message_parts.append(f"(Attached Image: {file_name})")
                # Store image data for attaching to the history message
                processed_image_file_bytes = file_bytes
                processed_image_file_name = file_name
                processed_this_file = True
                file_type = "image" # Make sure file_type is set here
                logger.info(f"Successfully processed image file: {file_name}")
            except Exception as e:
                logger.error(f"Error processing image file {file_name}: {str(e)}")
                st.error(f"Error processing image file {file_name}: {e}")
                user_display_message_parts.append(f"(Failed to process Image: {file_name})")

    if not user_api_content_parts:
        logger.warning("No processable content found")
        st.warning("No content to send. Please type a message or upload a processable file and ensure it's not empty.")
        st.stop()

    final_user_display_message = "\n".join(user_display_message_parts).strip()
    
    user_message_for_history = {"role": "user", "content": final_user_display_message}
    if processed_image_file_bytes and processed_image_file_name and file_type == "image":
        user_message_for_history["image_bytes_for_display"] = processed_image_file_bytes
        user_message_for_history["image_name_for_display"] = processed_image_file_name
        
    st.session_state.messages.append(user_message_for_history)

    # The immediate display of the user message is removed from here to prevent duplication.
    # It will be displayed by the loop at the top of the script after st.rerun().
    
    with st.spinner("DDC AI is thinking..."):
        api_call_messages = []
        system_prompt_in_payload = False
        for msg_idx, historic_msg in enumerate(st.session_state.messages):
            if historic_msg["role"] == "system":
                api_call_messages.append(historic_msg)
                system_prompt_in_payload = True
            elif historic_msg["role"] == "user":
                if msg_idx == len(st.session_state.messages) - 1:
                    api_call_messages.append({"role": "user", "content": user_api_content_parts})
                else: 
                    api_call_messages.append({"role": "user", "content": [{"type": "text", "text": historic_msg["content"]}]})
            elif historic_msg["role"] == "assistant":
                api_call_messages.append({"role": "assistant", "content": historic_msg["content"]})

        if not system_prompt_in_payload:
            api_call_messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
            
        try:
            logger.info("Preparing API request to OpenRouter using OpenAI client")
            logger.debug(f"API Request Messages: {json.dumps(api_call_messages, indent=2)}")
            
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_call_messages,
                extra_headers={
                    "HTTP-Referer": YOUR_SITE_URL,
                    "X-Title": YOUR_SITE_NAME,
                },
                extra_body={} # Added extra_body as per user's config
            )
            
            logger.info("Successfully received response from OpenRouter")
            assistant_response = None # Initialize
            if completion and completion.choices and len(completion.choices) > 0 and completion.choices[0].message:
                assistant_response = completion.choices[0].message.content
            else:
                logger.error(f"API response did not contain expected choices. Full response: {completion}")
                st.error("Received an unexpected or empty response from the AI. Please check the logs.")
                assistant_response = None # Ensure it's None if there's an issue
            
            logger.debug(f"Assistant Response: {assistant_response}")

            if assistant_response: # Only proceed if we have a valid response
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                # The immediate display of the assistant message is removed from here.
                # It will be displayed by the loop at the top of the script after st.rerun().
            else:
                # If assistant_response is still None, it means an error was logged.
                # We might not want to add an empty assistant message or rerun immediately.
                # For now, it will simply not display a new assistant message and rerun.
                pass
    
        except Exception as e:
            logger.error(f"Exception during API call: {str(e)}", exc_info=True)
            st.error(f"An error occurred with the API call: {str(e)}")
    
    st.rerun()

# To run this app:
# 1. Save as app.py
# 2. Make sure you have the required packages installed. Create a requirements.txt file with:
#    streamlit
#    requests
#    pandas
#    openpyxl
#    pdfplumber
#    openai # Added openai as it's used directly
#    Run: pip install -r requirements.txt
# 3. Run in your terminal: streamlit run app.py 
