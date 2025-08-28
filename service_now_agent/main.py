"""
FastAPI Application for Automated ServiceNow Ticket Creation from Gmail
Main application entry point with background scheduler for agentic workflow
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agents.scheduler import SchedulerAgent
from utils.logger import setup_logger
from tools.config_loader import ConfigLoader

# Setup logging
logger = setup_logger(__name__)

# Global scheduler instance
scheduler = None
scheduler_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown events"""
    global scheduler, scheduler_agent
    
    try:
        # Load configuration
        config = ConfigLoader()
        
        # Initialize scheduler agent
        scheduler_agent = SchedulerAgent(config)
        
        # Create and start the background scheduler
        scheduler = AsyncIOScheduler()
        
        # Add job to check emails every 10 minutes
        scheduler.add_job(
            func=scheduler_agent.trigger_workflow,
            trigger=IntervalTrigger(minutes=1),
            id='email_check_job',
            name='Check emails and process tickets',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("Background scheduler started - checking emails every 10 minutes")
        
        # Initial run
        asyncio.create_task(scheduler_agent.trigger_workflow())
        logger.info("Initial workflow triggered")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise
    finally:
        # Cleanup on shutdown
        if scheduler:
            scheduler.shutdown()
            logger.info("Background scheduler stopped")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="ServiceNow Ticket Automation",
    description="Automated ticket creation from Gmail emails using agentic AI workflow",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "message": "ServiceNow Ticket Automation Service is active",
        "scheduler_status": "running" if scheduler and scheduler.running else "stopped"
    }

@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    try:
        config_status = ConfigLoader().validate_config()
        return {
            "status": "healthy",
            "scheduler_running": scheduler.running if scheduler else False,
            "config_valid": config_status,
            "next_run": str(scheduler.get_job('email_check_job').next_run_time) if scheduler else None
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/trigger-manual")
async def trigger_manual():
    """Manual trigger endpoint for testing purposes"""
    try:
        if scheduler_agent:
            await scheduler_agent.trigger_workflow()
            return {"status": "success", "message": "Workflow triggered manually"}
        else:
            raise HTTPException(status_code=500, detail="Scheduler agent not initialized")
    except Exception as e:
        logger.error(f"Manual trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Manual trigger failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload in production
        log_level="info"
    )