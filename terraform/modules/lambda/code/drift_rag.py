import json
import boto3
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """
    Use Bedrock knowledge base to answer questions about drift history
    
    This function:
    1. Takes a question about infrastructure drift
    2. Uses Bedrock knowledge base to retrieve relevant drift reports
    3. Generates a response using RAG
    """
    
    # Initialize clients
    bedrock_agent = boto3.client('bedrock-agent-runtime')
    bedrock = boto3.client('bedrock-runtime')
    
    # Get knowledge base ID from environment variables
    knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
    retriever_id = os.environ.get('RETRIEVER_ID')
    model_id = os.environ.get('MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
    
    # Extract question from event
    question = event.get('question', '')
    if not question:
        return {
            'statusCode': 400,
            'body': 'No question provided'
        }
    
    try:
        # Query the knowledge base
        retrieve_response = bedrock_agent.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrieverId=retriever_id,
            retrievalQuery={
                'text': question
            },
            numberOfResults=5
        )
        
        # Extract retrieved passages
        retrieved_results = retrieve_response.get('retrievalResults', [])
        
        if not retrieved_results:
            return {
                'statusCode': 200,
                'body': {
                    'answer': 'No relevant drift history found for your question.',
                    'sources': []
                }
            }
        
        # Format retrieved passages for RAG
        context = "Here is information about past infrastructure drift:\n\n"
        sources = []
        
        for result in retrieved_results:
            content = result.get('content', {}).get('text', '')
            source_uri = result.get('location', {}).get('s3Location', {}).get('uri', '')
            if source_uri:
                source_name = source_uri.split('/')[-2]  # Extract drift ID from path
                sources.append({
                    'drift_id': source_name,
                    'uri': source_uri
                })
            context += f"{content}\n\n"
        
        # Create prompt for Bedrock
        prompt = f"""
You are an Infrastructure Drift Analyst. You help answer questions about past infrastructure drift events.
Use the following information about past drift events to answer the user's question.

Context:
{context}

User Question: {question}

Provide a detailed answer based on the context. If the context doesn't contain enough information to answer the question,
say so clearly. Include specific examples from past drift events when relevant. If you can identify patterns or trends
in the drift history, mention them.

For predictions about future drift, base your analysis on:
1. Past frequency of similar drift events
2. Common causes of drift in the history
3. Resources that tend to drift most often
4. Users or events associated with multiple drift incidents

Format your answer in a clear, structured way with sections and bullet points where appropriate.
"""
        
        # Call Bedrock
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )
        
        # Parse response
        result = json.loads(response['body'].read())
        answer = result['content'][0]['text']
        
        return {
            'statusCode': 200,
            'body': {
                'answer': answer,
                'sources': sources
            }
        }
    except Exception as e:
        error_msg = f"Error querying drift history: {str(e)}"
        print(error_msg)
        
        return {
            'statusCode': 500,
            'body': {
                'error': str(e)
            }
        }