<h1 align="center"> 
    🕷️ Web RAG 🕷️
</h1>

![](spider.jpg)

This project will help you to make a chatbot out of any website with atmost accuracy and speed. Just enter the website link, follow readme steps and in the end you can get a ready API for your chatbot.

<p align="center">
    <a href="https://python.org">
        <img src="http://forthebadge.com/images/badges/made-with-python.svg" alt="made-with-python">
    </a>
    <a href="https://github.com/ArshCypherZ">
        <img src="http://ForTheBadge.com/images/badges/built-with-love.svg" alt="built-with-love">
    </a> <br>
    <img src="https://img.shields.io/github/license/ArshCypherZ/HWBot?style=for-the-badge&logo=appveyor" alt="LICENSE">
    <img src="https://img.shields.io/github/forks/ArshCypherZ/HWBot?style=for-the-badge&logo=appveyor" alt="Forks">
    <img src="https://img.shields.io/github/stars/ArshCypherZ/HWBot?style=for-the-badge&logo=appveyor" alt="Stars">
</p>


<h2 align="center"> 
   ⇝ Working ⇜
</h2>

- Crawls every page and subpage
- Automatically extracts PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, TXT files
- Continues interrupted crawls from exact stopping point
- **Multi-document RAG**: 
  - Text documents → Vector embeddings + docstore
  - Tables → Summarized for embeddings, original stored in docstore
  - Smart retrieval system fetches relevant content for accurate responses

<h2 align="center"> 
   ⇝ Setup ⇜
</h2>

### Prerequisites

- Python 3.10+ (tested on 3.13)
- OpenAI API key (for embeddings and chat)
- LangChain API key (for tracing)
- HuggingFace ACCESS TOKEN (to upload and retrieve scraped content and db files)

### Installation

```bash
# Clone the repository
git clone https://github.com/ArshCypherZ/web-rag
cd web-rag

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
# Note: Tested on Arch Linux with Python 3.13, idk about windows, dont blame me

# Install dependencies
pip install -r requirements.txt
```


### Configuration File

Check `.env.example` for required environment variables.


<h2 align="center"> 
   ⇝ Complete Workflow ⇜
</h2>

### Step 1: Crawl a Website
```bash
python3 crawl.py https://example.com
```
This downloads all documents and content from the website.

### Step 2: Upload Content to HuggingFace
```bash
python3 upload.py
```
This uploads the scraped content to your HuggingFace repository.

### Step 3: Process Documents
**Run `meow.ipynb` notebook** - This is the core processing step that:
- Creates vector embeddings of all documents
- Generates the database files needed for RAG
- Uploads database files to HuggingFace (as `username/repo-name-dbfiles`)

**Recommended**: Run on Google Colab for better GPU access and processing power.

### Step 4: Use RAG System

First download database files from HuggingFace (check `rag.py` top comment for details).

```bash
# Local RAG interface
python3 rag.py

# OR start API server
python3 web_rag.py
# Access at: http://localhost:8000/query?question=your-question
```





## Additional Information

Should anything be not working, kindly let us know at [Spiral Tech Division](https://t.me/SpiralTechDivision) or simply open an issue.
If you want to contribute, we are happy to look at your pull request.

Run it on colab for better processing.
The notebook can be stopped and resumed, it tracks progress with SQLite.

I have already made several chatbots using this, like Google's Gemini documentation chatbot, Pipecat's documentation chatbot, chatbot for queries regarding Graphic Era Deemed to be University, and this has more potential, meaning, for any website you can create a RAG for it, which will obviously be accurate and fast.

More applications to this may include an AI assisted voice-to-voice app like for sales, admission queries, call centre, on which I am working on. If anyone would like to be a part of it, please email `arsh0javed@gmail.com` with your projects or your resume, doesn't really matter just flex on my email, will be happy to look :")

Thank You.