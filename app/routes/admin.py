"""
Admin API Routes for IVY AI Counsellor.

This module provides comprehensive admin endpoints for:
- Lead management and analytics
- PDF knowledge base management
- Gap report generation
- Conversation history and analytics
- System health monitoring
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
import aiosqlite
from zoneinfo import ZoneInfo

from app.models.database import DB_PATH, get_db
from app.models.schemas import LeadOut, PDFUploadOut, GapQueryOut
from app.services.pdf_service import ingest_pdf, delete_pdf_from_index, list_pdfs
from app.services.gap_report_service import generate_and_send_gap_report
from app.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

IST = ZoneInfo("Asia/Kolkata")

# ═══════════════════════════════════════════════════════════════════════════════
#  LEAD MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/leads", response_model=List[LeadOut])
async def get_all_leads(
    min_score: Optional[int] = Query(None, description="Filter by minimum lead score"),
    intent_level: Optional[str] = Query(None, description="Filter by intent level"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of leads to return"),
    offset: int = Query(0, ge=0, description="Number of leads to skip")
):
    """
    Get all leads with optional filtering and pagination.
    
    Query Parameters:
    - min_score: Filter leads with score >= this value
    - intent_level: Filter by intent level (BROWSING, RESEARCHING, CONSIDERING, HOT_LEAD)
    - limit: Maximum number of results (default: 100, max: 1000)
    - offset: Number of results to skip for pagination
    
    Returns:
    - List of leads sorted by lead_score (descending) and created_at (descending)
    """
    try:
        async with get_db() as db:
            db.row_factory = aiosqlite.Row
            
            # Build dynamic query
            query = "SELECT * FROM leads WHERE 1=1"
            params = []
            
            if min_score is not None:
                query += " AND lead_score >= ?"
                params.append(min_score)
            
            if intent_level:
                query += " AND intent_level = ?"
                params.append(intent_level.upper())
            
            query += " ORDER BY lead_score DESC, created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            leads = [dict(row) for row in rows]
            
            logger.info(f"Retrieved {len(leads)} leads (min_score={min_score}, intent={intent_level})")
            return leads
            
    except Exception as e:
        logger.error(f"Error fetching leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch leads: {str(e)}")


@router.get("/leads/{session_id}", response_model=LeadOut)
async def get_lead_by_session(session_id: str):
    """
    Get detailed information for a specific lead by session ID.
    
    Path Parameters:
    - session_id: Unique session identifier
    
    Returns:
    - Lead details including profile, conversation summary, and recommended actions
    """
    try:
        async with get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM leads WHERE session_id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail=f"Lead not found: {session_id}")
            
            return dict(row)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching lead {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch lead: {str(e)}")


@router.get("/leads/stats/summary")
async def get_lead_statistics():
    """
    Get comprehensive lead statistics and analytics.
    
    Returns:
    - total_leads: Total number of leads
    - hot_leads: Number of hot leads (score >= 80)
    - avg_lead_score: Average lead score
    - intent_distribution: Count of leads by intent level
    - leads_by_country: Count of leads by target country
    - leads_by_course: Count of leads by target course
    - recent_hot_leads: Last 10 hot leads
    """
    try:
        async with get_db() as db:
            db.row_factory = aiosqlite.Row
            
            # Total leads
            cursor = await db.execute("SELECT COUNT(*) as count FROM leads")
            total_leads = (await cursor.fetchone())["count"]
            
            # Hot leads (score >= 80)
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM leads WHERE lead_score >= ?",
                (settings.HOT_LEAD_SCORE_THRESHOLD,)
            )
            hot_leads = (await cursor.fetchone())["count"]
            
            # Average lead score
            cursor = await db.execute("SELECT AVG(lead_score) as avg_score FROM leads")
            avg_score = (await cursor.fetchone())["avg_score"] or 0
            
            # Intent distribution
            cursor = await db.execute(
                """SELECT intent_level, COUNT(*) as count 
                   FROM leads 
                   GROUP BY intent_level 
                   ORDER BY count DESC"""
            )
            intent_dist = {row["intent_level"]: row["count"] for row in await cursor.fetchall()}
            
            # Leads by country
            cursor = await db.execute(
                """SELECT target_country, COUNT(*) as count 
                   FROM leads 
                   WHERE target_country IS NOT NULL 
                   GROUP BY target_country 
                   ORDER BY count DESC 
                   LIMIT 10"""
            )
            country_dist = {row["target_country"]: row["count"] for row in await cursor.fetchall()}
            
            # Leads by course
            cursor = await db.execute(
                """SELECT target_course, COUNT(*) as count 
                   FROM leads 
                   WHERE target_course IS NOT NULL 
                   GROUP BY target_course 
                   ORDER BY count DESC 
                   LIMIT 10"""
            )
            course_dist = {row["target_course"]: row["count"] for row in await cursor.fetchall()}
            
            # Recent hot leads
            cursor = await db.execute(
                """SELECT session_id, name, email, phone, lead_score, intent_level, created_at
                   FROM leads 
                   WHERE lead_score >= ? 
                   ORDER BY created_at DESC 
                   LIMIT 10""",
                (settings.HOT_LEAD_SCORE_THRESHOLD,)
            )
            recent_hot = [dict(row) for row in await cursor.fetchall()]
            
            return {
                "total_leads": total_leads,
                "hot_leads": hot_leads,
                "avg_lead_score": round(avg_score, 2),
                "intent_distribution": intent_dist,
                "leads_by_country": country_dist,
                "leads_by_course": course_dist,
                "recent_hot_leads": recent_hot,
                "generated_at": datetime.now(IST).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error generating lead statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate statistics: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
#  CONVERSATION HISTORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/conversations/{session_id}")
async def get_conversation_history(session_id: str):
    """
    Get complete conversation history for a specific session.
    
    Path Parameters:
    - session_id: Unique session identifier
    
    Returns:
    - List of conversation messages with metadata (intent, scores, timestamps)
    """
    try:
        async with get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT id, session_id, user_message, ai_response, 
                          intent_level, lead_score, rag_score, fallback_type, 
                          platform, timestamp
                   FROM conversations 
                   WHERE session_id = ? 
                   ORDER BY timestamp ASC""",
                (session_id,)
            )
            rows = await cursor.fetchall()
            
            if not rows:
                raise HTTPException(status_code=404, detail=f"No conversations found for session: {session_id}")
            
            conversations = [dict(row) for row in rows]
            
            return {
                "session_id": session_id,
                "message_count": len(conversations),
                "conversations": conversations
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {str(e)}")


@router.get("/conversations/stats/summary")
async def get_conversation_statistics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze")
):
    """
    Get conversation statistics for the specified time period.
    
    Query Parameters:
    - days: Number of days to analyze (default: 7, max: 90)
    
    Returns:
    - total_conversations: Total number of conversations
    - unique_sessions: Number of unique sessions
    - avg_messages_per_session: Average messages per session
    - fallback_rate: Percentage of messages that triggered fallback
    - platform_distribution: Count by platform (web, whatsapp)
    - hourly_distribution: Conversation count by hour of day
    """
    try:
        since = (datetime.now(IST) - timedelta(days=days)).strftime("%Y-%m-%d")
        
        async with get_db() as db:
            db.row_factory = aiosqlite.Row
            
            # Total conversations
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM conversations WHERE date(timestamp) >= date(?)",
                (since,)
            )
            total_convs = (await cursor.fetchone())["count"]
            
            # Unique sessions
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT session_id) as count FROM conversations WHERE date(timestamp) >= date(?)",
                (since,)
            )
            unique_sessions = (await cursor.fetchone())["count"]
            
            # Average messages per session
            avg_messages = round(total_convs / unique_sessions, 2) if unique_sessions > 0 else 0
            
            # Fallback rate
            cursor = await db.execute(
                """SELECT COUNT(*) as count FROM conversations 
                   WHERE date(timestamp) >= date(?) AND fallback_type IS NOT NULL""",
                (since,)
            )
            fallback_count = (await cursor.fetchone())["count"]
            fallback_rate = round((fallback_count / total_convs * 100), 2) if total_convs > 0 else 0
            
            # Platform distribution
            cursor = await db.execute(
                """SELECT platform, COUNT(*) as count 
                   FROM conversations 
                   WHERE date(timestamp) >= date(?) 
                   GROUP BY platform""",
                (since,)
            )
            platform_dist = {row["platform"]: row["count"] for row in await cursor.fetchall()}
            
            # Hourly distribution
            cursor = await db.execute(
                """SELECT strftime('%H', timestamp) as hour, COUNT(*) as count 
                   FROM conversations 
                   WHERE date(timestamp) >= date(?) 
                   GROUP BY hour 
                   ORDER BY hour""",
                (since,)
            )
            hourly_dist = {int(row["hour"]): row["count"] for row in await cursor.fetchall()}
            
            return {
                "period_days": days,
                "total_conversations": total_convs,
                "unique_sessions": unique_sessions,
                "avg_messages_per_session": avg_messages,
                "fallback_rate_percent": fallback_rate,
                "platform_distribution": platform_dist,
                "hourly_distribution": hourly_dist,
                "generated_at": datetime.now(IST).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error generating conversation statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate statistics: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF KNOWLEDGE BASE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/pdfs/upload")
async def upload_pdf(
    file: UploadFile = File(..., description="PDF file to upload"),
    category: str = Form(..., description="Document category (visa/university/scholarship/testprep/finance/poststudy/sop)"),
    country: Optional[str] = Form(None, description="Target country (optional)")
):
    """
    Upload and ingest a PDF into the knowledge base.
    
    This endpoint:
    1. Validates the PDF file
    2. Extracts text from all pages
    3. Chunks text using tiktoken (512 tokens, 50 overlap)
    4. Generates embeddings using OpenAI
    5. Stores vectors in Pinecone
    6. Saves metadata to database
    
    Form Parameters:
    - file: PDF file (max 50MB)
    - category: Document category (visa/university/scholarship/testprep/finance/poststudy/sop)
    - country: Target country (optional, for filtering)
    
    Returns:
    - Detailed ingestion summary including chunk count and processing time
    """
    import os
    import tempfile
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Validate category
    valid_categories = {"visa", "university", "scholarship", "testprep", "finance", "poststudy", "sop"}
    if category.lower() not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Valid options: {', '.join(sorted(valid_categories))}"
        )
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        logger.info(f"Processing PDF upload: {file.filename} (category: {category})")
        
        # Ingest PDF
        summary = await ingest_pdf(
            file_path=tmp_path,
            filename=file.filename,
            category=category.lower()
        )
        
        # Clean up temporary file
        os.unlink(tmp_path)
        
        return {
            "success": True,
            "message": f"PDF ingested successfully: {summary.total_chunks} chunks created",
            "pdf_id": summary.pdf_id,
            "filename": summary.filename,
            "category": summary.category,
            "total_pages": summary.total_pages,
            "pages_processed": summary.pages_processed,
            "pages_skipped": summary.pages_skipped,
            "total_chunks": summary.total_chunks,
            "time_taken_seconds": summary.time_taken_seconds
        }
        
    except Exception as e:
        # Clean up temporary file on error
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        logger.error(f"PDF upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF ingestion failed: {str(e)}")


@router.get("/pdfs", response_model=List[PDFUploadOut])
async def list_all_pdfs():
    """
    List all PDFs in the knowledge base.
    
    Returns:
    - List of all active PDFs with metadata (filename, category, chunk count, upload date)
    """
    try:
        pdfs = await list_pdfs()
        logger.info(f"Retrieved {len(pdfs)} PDFs from knowledge base")
        return pdfs
        
    except Exception as e:
        logger.error(f"Error listing PDFs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list PDFs: {str(e)}")


@router.delete("/pdfs/{pdf_id}")
async def delete_pdf(pdf_id: str):
    """
    Delete a PDF from the knowledge base.
    
    This endpoint:
    1. Removes all vectors from Pinecone
    2. Marks PDF as deleted in database
    
    Path Parameters:
    - pdf_id: Unique PDF identifier
    
    Returns:
    - Success confirmation
    """
    try:
        success = await delete_pdf_from_index(pdf_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete PDF")
        
        logger.info(f"PDF deleted successfully: {pdf_id}")
        return {
            "success": True,
            "message": f"PDF deleted successfully: {pdf_id}",
            "pdf_id": pdf_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting PDF {pdf_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete PDF: {str(e)}")


@router.get("/pdfs/stats/summary")
async def get_pdf_statistics():
    """
    Get PDF knowledge base statistics.
    
    Returns:
    - total_pdfs: Total number of active PDFs
    - total_chunks: Total number of text chunks
    - pdfs_by_category: Count of PDFs by category
    - avg_chunks_per_pdf: Average chunks per PDF
    - recent_uploads: Last 10 uploaded PDFs
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Total PDFs
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM pdf_library WHERE status = 'ACTIVE'"
            )
            total_pdfs = (await cursor.fetchone())["count"]
            
            # Total chunks
            cursor = await db.execute(
                "SELECT SUM(chunk_count) as total FROM pdf_library WHERE status = 'ACTIVE'"
            )
            total_chunks = (await cursor.fetchone())["total"] or 0
            
            # PDFs by category
            cursor = await db.execute(
                """SELECT category, COUNT(*) as count 
                   FROM pdf_library 
                   WHERE status = 'ACTIVE' 
                   GROUP BY category 
                   ORDER BY count DESC"""
            )
            category_dist = {row["category"]: row["count"] for row in await cursor.fetchall()}
            
            # Average chunks per PDF
            avg_chunks = round(total_chunks / total_pdfs, 2) if total_pdfs > 0 else 0
            
            # Recent uploads
            cursor = await db.execute(
                """SELECT pdf_id, filename, category, chunk_count, upload_date
                   FROM pdf_library 
                   WHERE status = 'ACTIVE' 
                   ORDER BY upload_date DESC 
                   LIMIT 10"""
            )
            recent_uploads = [dict(row) for row in await cursor.fetchall()]
            
            return {
                "total_pdfs": total_pdfs,
                "total_chunks": total_chunks,
                "pdfs_by_category": category_dist,
                "avg_chunks_per_pdf": avg_chunks,
                "recent_uploads": recent_uploads,
                "generated_at": datetime.now(IST).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error generating PDF statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate statistics: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
#  GAP REPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/gap-report")
async def trigger_gap_report(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze")
):
    """
    Manually trigger gap report generation and email.
    
    This endpoint:
    1. Fetches unanswered queries from last N days
    2. Groups queries by topic using keyword matching
    3. Ranks topics by frequency
    4. Generates HTML email report
    5. Sends email to admin
    6. Marks queries as notified
    
    Query Parameters:
    - days: Number of days to analyze (default: 7, max: 30)
    
    Returns:
    - Detailed report summary including top 10 topics
    """
    try:
        logger.info(f"Manual gap report triggered for last {days} days")
        result = await generate_and_send_gap_report(days=days)
        
        return result
        
    except Exception as e:
        logger.error(f"Gap report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gap report failed: {str(e)}")


@router.get("/unanswered-queries", response_model=List[GapQueryOut])
async def get_unanswered_queries(
    days: int = Query(7, ge=1, le=90, description="Number of days to fetch"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of queries")
):
    """
    Get list of unanswered queries (queries that triggered fallback).
    
    Query Parameters:
    - days: Number of days to fetch (default: 7, max: 90)
    - limit: Maximum number of queries (default: 100, max: 1000)
    
    Returns:
    - List of unanswered queries with frequency count
    """
    try:
        since = (datetime.now(IST) - timedelta(days=days)).strftime("%Y-%m-%d")
        
        async with get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT query_text, COUNT(*) as frequency, fallback_type
                   FROM unanswered_queries 
                   WHERE date(timestamp) >= date(?) 
                   GROUP BY query_text 
                   ORDER BY frequency DESC 
                   LIMIT ?""",
                (since, limit)
            )
            rows = await cursor.fetchall()
            
            queries = [dict(row) for row in rows]
            
            logger.info(f"Retrieved {len(queries)} unanswered queries from last {days} days")
            return queries
            
    except Exception as e:
        logger.error(f"Error fetching unanswered queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch queries: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM HEALTH & MONITORING
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def admin_health_check():
    """
    Comprehensive system health check for admin monitoring.
    
    Returns:
    - Database connectivity status
    - Pinecone connectivity status
    - Recent activity metrics
    - System configuration
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(IST).isoformat(),
        "checks": {}
    }
    
    # Check database
    try:
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) as count FROM leads")
            lead_count = (await cursor.fetchone())[0]
            health_status["checks"]["database"] = {
                "status": "healthy",
                "lead_count": lead_count
            }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check Pinecone
    try:
        from app.services.pdf_service import _get_pinecone_index
        index = _get_pinecone_index()
        stats = index.describe_index_stats()
        health_status["checks"]["pinecone"] = {
            "status": "healthy",
            "total_vectors": stats.total_vector_count
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["pinecone"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Recent activity (last 24 hours)
    try:
        since = (datetime.now(IST) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM conversations WHERE timestamp >= ?",
                (since,)
            )
            recent_convs = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM leads WHERE created_at >= ?",
                (since,)
            )
            recent_leads = (await cursor.fetchone())[0]
            
            health_status["checks"]["recent_activity"] = {
                "status": "healthy",
                "conversations_24h": recent_convs,
                "leads_24h": recent_leads
            }
    except Exception as e:
        health_status["checks"]["recent_activity"] = {
            "status": "error",
            "error": str(e)
        }
    
    # System configuration
    health_status["configuration"] = {
        "environment": settings.ENVIRONMENT,
        "debug_mode": settings.DEBUG,
        "rag_top_k": settings.RAG_TOP_K,
        "similarity_threshold": settings.RAG_SIMILARITY_THRESHOLD,
        "hot_lead_threshold": settings.HOT_LEAD_SCORE_THRESHOLD
    }
    
    return health_status


@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """
    Get comprehensive dashboard summary for admin overview.
    
    Returns:
    - Lead statistics
    - Conversation statistics
    - PDF knowledge base statistics
    - Recent activity
    - System health
    """
    try:
        # Get all statistics in parallel
        lead_stats = await get_lead_statistics()
        conv_stats = await get_conversation_statistics(days=7)
        pdf_stats = await get_pdf_statistics()
        
        # Recent hot leads
        async with get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT session_id, name, email, phone, lead_score, 
                          intent_level, target_country, target_course, created_at
                   FROM leads 
                   WHERE lead_score >= ? 
                   ORDER BY created_at DESC 
                   LIMIT 5""",
                (settings.HOT_LEAD_SCORE_THRESHOLD,)
            )
            recent_hot_leads = [dict(row) for row in await cursor.fetchall()]
        
        return {
            "generated_at": datetime.now(IST).isoformat(),
            "leads": {
                "total": lead_stats["total_leads"],
                "hot_leads": lead_stats["hot_leads"],
                "avg_score": lead_stats["avg_lead_score"],
                "intent_distribution": lead_stats["intent_distribution"],
                "recent_hot": recent_hot_leads
            },
            "conversations": {
                "total_last_7_days": conv_stats["total_conversations"],
                "unique_sessions": conv_stats["unique_sessions"],
                "avg_messages_per_session": conv_stats["avg_messages_per_session"],
                "fallback_rate": conv_stats["fallback_rate_percent"]
            },
            "knowledge_base": {
                "total_pdfs": pdf_stats["total_pdfs"],
                "total_chunks": pdf_stats["total_chunks"],
                "pdfs_by_category": pdf_stats["pdfs_by_category"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating dashboard summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard: {str(e)}")
