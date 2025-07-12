from fastapi import FastAPI, HTTPException
import uvicorn
from rag import query_rag

app = FastAPI()

@app.get("/query")
async def query(question: str):
    """
    Endpoint to query the RAG system with a question.
    """
    try:
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        response = await query_rag(question)
        return {"response": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0", port=8000)
    logger.info("FastAPI server is running.")
