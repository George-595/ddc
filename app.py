import streamlit as st
from openai import OpenAI
import pandas as pd
import pdfplumber
import io

# Configuration
OPENROUTER_API_KEY = "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"
YOUR_SITE_URL = "https://www.ddcfoods.co.uk"
YOUR_SITE_NAME = "DDC Foods AI Assistant"
MODEL_NAME = "google/gemini-2.0-flash-exp:free"

SYSTEM_PROMPT = """✅ SYSTEM PROMPT – DDC FOODS AI ASSISTANT

You are an AI assistant representing DDC Foods Ltd, a UK-based food and drink distributor. You are used internally by staff and externally on the website. Your knowledge reflects the company's operations, values, and product catalogue as of 2025.

⸻

🏢 COMPANY PROFILE
	•	Name: DDC Foods Ltd
	•	Founded: 1996
	•	Location: Maylands House, Maylands Avenue, Hemel Hempstead, Hertfordshire, HP2 7DE, United Kingdom
	•	Website: www.ddcfoods.co.uk
	•	Revenue: £25.46 million (as of April 2024)
	•	Employees: Approximately 80
	•	Distribution: 97% UK national coverage using own fleet
	•	Next-Day Delivery: Available inside M25 for weekday orders placed before 12pm

⸻

🌱 SUSTAINABILITY
	•	DDC Foods is committed to reducing its carbon footprint, maintaining sustainable sourcing, and conducting environmental risk assessments.
	•	Product and supplier choices are made with sustainability, health trends, and innovation in mind.

⸻

🛍️ PRODUCT CATEGORIES & FEATURES

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

You must always provide clear allergen and dietary suitability when asked. Key dietary categories:
	•	Vegetarian
	•	Vegan
	•	Gluten-free
	•	Dairy-free
	•	Nut-free
	•	Kosher
	•	Halal

All products are clearly labelled and compliant with UK food labelling regulations.

⸻

🤖 USAGE INSTRUCTIONS FOR AI

Internal Use (Staff):
	•	Assist with order lookup, stock levels, product attributes, dietary filtering.
	•	Help sales teams recommend products based on customer profile.
	•	Retrieve allergen data quickly.
	•	Use official brand partnerships to identify product alternatives.

Website-Facing Use (Public):
	•	Answer product-related queries clearly and concisely.
	•	Support filtering by dietary need, brand, or pack size.
	•	Always align responses with DDC Foods' tone: professional, helpful, and informed.
	•	Provide next-day delivery info if user location is within M25 and order is placed before noon on weekdays.

⸻

🔗 REFERENCES

Live data can be cross-verified via:
	•	www.ddcfoods.co.uk
	•	DDC Product Pages
	•	Brand-specific pages (e.g., KIND, The Collective)
"""

# Initialize OpenAI client
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

# Streamlit app title
st.title(YOUR_SITE_NAME)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Chat input and file upload form
with st.form(key="chat_form"):
    user_text_prompt = st.text_input("Your message:", key="user_prompt_text_key")
    uploaded_excel = st.file_uploader("Upload Excel file (optional)", type=["xlsx", "xls"], key="excel_uploader_key")
    uploaded_pdf = st.file_uploader("Upload PDF file (optional)", type=["pdf"], key="pdf_uploader_key")
    submit_button = st.form_submit_button(label="Send / Process Files")

if submit_button:
    if not user_text_prompt.strip() and not uploaded_excel and not uploaded_pdf:
        st.warning("Please enter a message or upload a file.")
        st.stop() # Use st.stop() to halt execution for this run if nothing is submitted

    user_api_content_parts = []
    user_display_message_parts = []

    if user_text_prompt.strip():
        user_api_content_parts.append({"type": "text", "text": user_text_prompt})
        user_display_message_parts.append(user_text_prompt)

    # Process Excel file
    if uploaded_excel:
        try:
            excel_file_bytes = uploaded_excel.getvalue()
            df = pd.read_excel(io.BytesIO(excel_file_bytes))
            excel_json = df.to_json(orient="records", indent=2)
            excel_content_for_api = f"--- Content from Excel file: {uploaded_excel.name} ---\n{excel_json}"
            user_api_content_parts.append({"type": "text", "text": excel_content_for_api})
            user_display_message_parts.append(f"(Attached Excel: {uploaded_excel.name})")
            # st.success(f"Processed Excel file: {uploaded_excel.name}") # Success message can be distracting if form reruns
        except Exception as e:
            st.error(f"Error processing Excel file {uploaded_excel.name}: {e}")
            user_display_message_parts.append(f"(Failed to process Excel: {uploaded_excel.name})")

    # Process PDF file
    if uploaded_pdf:
        try:
            pdf_file_bytes = uploaded_pdf.getvalue()
            pdf_text_parts = []
            with pdfplumber.open(io.BytesIO(pdf_file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text and page_text.strip():  # Make sure text was extracted and is not just whitespace
                        pdf_text_parts.append(f"--- Page {page_num + 1} of {uploaded_pdf.name} ---\n{page_text.strip()}")
            
            if not pdf_text_parts:
                pdf_content_for_api = f"--- No text could be extracted from PDF file: {uploaded_pdf.name} ---"
            else:
                pdf_content_for_api = f"--- Content from PDF file: {uploaded_pdf.name} ---
" + "\n\n".join(pdf_text_parts)
            
            user_api_content_parts.append({"type": "text", "text": pdf_content_for_api})
            user_display_message_parts.append(f"(Attached PDF: {uploaded_pdf.name})")
            # st.success(f"Processed PDF file: {uploaded_pdf.name}")
        except Exception as e:
            st.error(f"Error processing PDF file {uploaded_pdf.name}: {e}")
            user_display_message_parts.append(f"(Failed to process PDF: {uploaded_pdf.name})")

    if not user_api_content_parts: # If no text prompt and file processing failed or no files
        st.warning("No content to send. Please type a message or ensure files are processable.")
        st.stop()

    final_user_display_message = "\n".join(user_display_message_parts).strip()
    st.session_state.messages.append({"role": "user", "content": final_user_display_message})

    with st.chat_message("user"):
        st.markdown(final_user_display_message)
    
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
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": YOUR_SITE_URL,
                "X-Title": YOUR_SITE_NAME,
            },
            model=MODEL_NAME,
            messages=api_call_messages
        )
        response = completion.choices[0].message.content

        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

    except Exception as e:
        st.error(f"An error occurred with the API call: {e}")
    
    st.experimental_rerun()

# To run this app:
# 1. Save as app.py
# 2. Make sure you have the required packages installed. Create a requirements.txt file with:
#    streamlit
#    openai
#    pandas
#    openpyxl
#    pdfplumber
#    Run: pip install -r requirements.txt
# 3. Run in your terminal: streamlit run app.py 