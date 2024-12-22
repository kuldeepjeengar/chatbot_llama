import chainlit as cl
from groq import Groq
import base64
from io import BytesIO
from chainlit.element import ElementBased
import tempfile
import os
from PyPDF2 import PdfReader
import chromadb
from chromadb.utils import embedding_functions
import uuid

client = Groq()

settings = {
    "model": "llama-3.2-90b-vision-preview",
    "temperature": 0.7,
    "max_tokens": 7000,
    "top_p": 1
}

# Initialize ChromaDB
chroma_client = chromadb.Client()
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
collection = chroma_client.create_collection(
    name="pdf_collection",
    embedding_function=embedding_function
)

def process_pdf(file_path):
    """Extract text from PDF and split into chunks."""
    reader = PdfReader(file_path)
    text_chunks = []
    
    for page in reader.pages:
        text = page.extract_text()
        # Split text into smaller chunks (roughly 1000 characters each)
        words = text.split()
        chunk_size = 200  # approximate words per chunk
        
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():  # Only add non-empty chunks
                text_chunks.append(chunk)
    
    return text_chunks

def store_in_chromadb(chunks, pdf_name):
    """Store text chunks in ChromaDB with metadata."""
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadata = [{"source": pdf_name, "chunk_index": i} for i, _ in enumerate(chunks)]
    
    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadata
    )

async def query_pdf_knowledge(query, k=3):
    """Query the PDF knowledge base and return relevant chunks."""
    results = collection.query(
        query_texts=[query],
        n_results=k
    )
    
    if results and results['documents']:
        return results['documents'][0]  # Return the most relevant chunks
    return []

@cl.on_chat_start
def start_chat():
    # Initialize message history
    cl.user_session.set(
        "message_history",
        [{"role": "system", "content": "You are a helpful assistant. You can answer questions based on the PDFs that have been uploaded and your general knowledge."}],
    )

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.AudioChunk):
    if chunk.isStart:
        buffer = BytesIO()
        buffer.name = f"input_audio.{chunk.mimeType.split('/')[1]}"
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", chunk.mimeType)

    # Write audio chunks to the buffer
    cl.user_session.get("audio_buffer").write(chunk.data)

@cl.on_audio_end
async def on_audio_end(elements: list[ElementBased]):
    try:
        # Retrieve audio buffer
        audio_buffer: BytesIO = cl.user_session.get("audio_buffer")
        audio_buffer.seek(0)
        audio_file = audio_buffer.read()

        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as temp_file:
            temp_file.write(audio_file)
            temp_filename = temp_file.name

        try:
            with open(temp_filename, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(temp_filename, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                )

                transcription_text = transcription.text

                message_history = cl.user_session.get("message_history")
                message_history.append({
                    "role": "user",
                    "content": transcription_text
                })
                cl.user_session.set("message_history", message_history)

                await cl.Message(
                    content=f"🗣️ [Audio Query] {transcription_text}"
                ).send()

                await process_query(transcription_text)

        finally:
            os.unlink(temp_filename)

    except Exception as e:
        await cl.Message(content=f"Error processing audio: {str(e)}").send()

@cl.on_message
async def main(message: cl.Message):
    message_history = cl.user_session.get("message_history")

    if message.elements:
        element = message.elements[0]
        if element.name.lower().endswith('.pdf'):
            await handle_pdf(message, element, message_history)
        elif element.name.lower().endswith(('.jpg', '.jpeg', '.png')):
            await handle_image(message, element, message_history)
    else:
        message_history.append({"role": "user", "content": message.content})
        cl.user_session.set("message_history", message_history)
        await process_query(message.content)

async def handle_pdf(message, pdf_element, message_history):
    try:
        # Process the PDF
        text_chunks = process_pdf(pdf_element.path)
        
        # Store in ChromaDB
        store_in_chromadb(text_chunks, pdf_element.name)
        
        # Update message history
        message_history.append({
            "role": "user",
            "content": f"[PDF uploaded] {pdf_element.name}"
        })
        
        response = f"📄 Successfully processed PDF: {pdf_element.name}\nExtracted {len(text_chunks)} text chunks.\nYou can now ask questions about this document!"
        
        message_history.append({"role": "assistant", "content": response})
        cl.user_session.set("message_history", message_history)
        
        await cl.Message(content=response).send()

    except Exception as e:
        await cl.Message(content=f"Error processing PDF: {str(e)}").send()

async def handle_image(message, image_element, message_history):
    try:
        with open(image_element.path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")
            image_data_url = f"data:image/jpeg;base64,{base64_image}"

        stream = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": message.content if message.content else "Please describe this image."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url
                            }
                        }
                    ]
                }
            ],
            temperature=0,
            max_tokens=6000,
            top_p=1,
            stream=False,
            stop=None,
        )

        response_content = stream.choices[0].message.content

        message_history.append({
            "role": "user",
            "content": f"[Image uploaded] {response_content or 'Please describe this image.'}"
        })
        message_history.append({"role": "assistant", "content": response_content})
        cl.user_session.set("message_history", message_history)

        await cl.Message(content=response_content).send()

    except Exception as e:
        await cl.Message(content=f"Error processing image: {str(e)}").send()

async def process_query(query):
    """Processes a user query, incorporating PDF knowledge when relevant."""
    message_history = cl.user_session.get("message_history")
    msg = cl.Message(content="")

    try:
        # Query the PDF knowledge base
        relevant_chunks = await query_pdf_knowledge(query)
        
        # Prepare the context for the model
        context = "\n".join(relevant_chunks) if relevant_chunks else ""
        
        # Prepare the messages with context if available
        messages = message_history.copy()
        if context:
            messages.append({
                "role": "system",
                "content": f"Here is relevant information from the uploaded PDFs:\n{context}\n\nPlease use this information along with your knowledge to answer the question."
            })
        
        # Use the text model to process the query
        stream = client.chat.completions.create(
            model=settings["model"],
            messages=messages,
            temperature=settings["temperature"],
            max_tokens=settings["max_tokens"],
            top_p=settings["top_p"],
            stream=True,
            stop=None
        )

        for part in stream:
            if token := part.choices[0].delta.content or "":
                await msg.stream_token(token)

        # Add assistant's response to history
        message_history.append({"role": "assistant", "content": msg.content})
        cl.user_session.set("message_history", message_history)

        await msg.update()

    except Exception as e:
        await cl.Message(content=f"Error processing query: {str(e)}").send()