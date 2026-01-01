#!/usr/bin/env python3
"""Test script for interview API endpoints."""

import json
import sys
from typing import Any

import httpx


BASE_URL = "http://127.0.0.1:8001"


def test_generate():
    """Test question generation endpoint."""
    print("=" * 60)
    print("Testing POST /api/v1/interviews/generate")
    print("=" * 60)
    
    payload = {
        "profile": {
            "role": "Software Engineer",
            "level": "Senior",
            "stack": ["Python", "FastAPI", "PostgreSQL"],
            "mode": "conversation"
        },
        "count": 3,
        "existing_questions": []
    }
    
    try:
        response = httpx.post(
            f"{BASE_URL}/api/v1/interviews/generate",
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Success! Session ID: {data['fastapi_session_id']}")
        print(f"Generated {len(data['questions'])} questions:\n")
        for i, q in enumerate(data['questions'], 1):
            print(f"  {i}. {q}")
        
        return data['fastapi_session_id']
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_evaluate(session_id: str | None):
    """Test evaluation endpoint."""
    print("\n" + "=" * 60)
    print("Testing POST /api/v1/interviews/evaluate")
    print("=" * 60)
    
    if not session_id:
        session_id = "test_session_123"
        print(f"⚠️  No session ID from generate, using: {session_id}")
    
    payload = {
        "fastapi_session_id": session_id,
        "mode": "conversation",
        "items": [
            {
                "order": 1,
                "question": "What is the difference between a list and a tuple in Python?",
                "answer": "A list is mutable and uses square brackets, while a tuple is immutable and uses parentheses. Lists are better for collections that need to change, tuples for fixed data."
            },
            {
                "order": 2,
                "question": "Explain how FastAPI handles async requests.",
                "answer": "FastAPI uses async/await syntax and can handle concurrent requests efficiently using Python's asyncio. It supports both sync and async route handlers."
            }
        ],
        "context": {},
        "include_summary": True
    }
    
    try:
        response = httpx.post(
            f"{BASE_URL}/api/v1/interviews/evaluate",
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        
        data = response.json()
        print("✅ Success!")
        print(f"\nQuestion Evaluations ({len(data['results'])}):")
        for r in data['results']:
            print(f"\n  Order {r['order']}:")
            print(f"    Score: {r['score']}/10")
            print(f"    Feedback: {r['feedback']}")
            print(f"    Meta: {r['meta']}")
        
        if data.get('overall'):
            print(f"\nOverall Evaluation:")
            print(f"  Score: {data['overall']['score']}/10")
            print(f"  Feedback: {data['overall']['feedback']}")
            print(f"  Meta: {data['overall']['meta']}")
        
        return True
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n🚀 Testing Interview API\n")
    
    # Check if server is running
    try:
        response = httpx.get(f"{BASE_URL}/docs", timeout=5.0)
        print("✅ Server is running\n")
    except Exception:
        print("❌ Server is not running!")
        print(f"   Please start it with: uvicorn app.main:app --reload --port 8001")
        sys.exit(1)
    
    # Test generation
    session_id = test_generate()
    
    # Test evaluation
    test_evaluate(session_id)
    
    print("\n" + "=" * 60)
    print("✅ Tests complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

