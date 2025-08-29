import streamlit as st
import time
import threading
import asyncio
from datetime import datetime
from typing import Dict, Any, List
import json
import sys
import os
import traceback
from contextlib import contextmanager

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import your agents
try:
    from agents.scheduler import SchedulerAgent
    from agents.mail_fetcher import MailFetcherAgent
    from agents.classifier import ClassifierAgent
    from agents.summary import SummaryAgent
    from agents.category_extractor import CategoryExtractorAgent
    from agents.servicenow import ServiceNowAgent
    from agents.notification import NotificationAgent
    from agents.tracker import TrackerAgent
    from tools.config_loader import ConfigLoader
    IMPORTS_SUCCESS = True
    IMPORT_ERROR = None
except ImportError as e:
    IMPORTS_SUCCESS = False
    IMPORT_ERROR = str(e)

class WorkflowManager:
    """Manages workflow execution and state"""
    
    def __init__(self):
        self.agents = {}
        self.config = None
        self.scheduler = None
        
    def initialize_agents(self, status_callback=None):
        """Initialize all agents"""
        try:
            if status_callback:
                status_callback("Loading configuration...")
            
            self.config = ConfigLoader()
            
            # Initialize agents
            agent_classes = [
                ('mail_fetcher', MailFetcherAgent, 'Mail Fetcher'),
                ('classifier', ClassifierAgent, 'Classifier'),
                ('summary', SummaryAgent, 'Summary Agent'),
                ('category_extractor', CategoryExtractorAgent, 'Category Extractor'),
                ('servicenow', ServiceNowAgent, 'ServiceNow Agent'),
                ('notification', NotificationAgent, 'Notification Agent'),
                ('tracker', TrackerAgent, 'Tracker Agent')
            ]
            
            for agent_key, agent_class, agent_name in agent_classes:
                try:
                    if status_callback:
                        status_callback(f"Initializing {agent_name}...")
                    
                    agent = agent_class(self.config)
                    self.agents[agent_key] = agent
                    
                    if status_callback:
                        status_callback(f"✅ {agent_name} initialized")
                        
                except Exception as e:
                    error_msg = f"❌ Failed to initialize {agent_name}: {str(e)}"
                    if status_callback:
                        status_callback(error_msg)
                    raise e
            
            # Initialize scheduler
            if status_callback:
                status_callback("Initializing scheduler...")
            
            self.scheduler = SchedulerAgent(self.config)
            
            # Assign agents to scheduler
            self.scheduler.mail_fetcher = self.agents['mail_fetcher']
            self.scheduler.classifier = self.agents['classifier']
            self.scheduler.summary = self.agents['summary']
            self.scheduler.category_extractor = self.agents['category_extractor']
            self.scheduler.servicenow = self.agents['servicenow']
            self.scheduler.notification = self.agents['notification']
            self.scheduler.tracker = self.agents['tracker']
            
            if status_callback:
                status_callback("🎉 All agents initialized successfully!")
            
            return True, "Success"
            
        except Exception as e:
            error_msg = f"Failed to initialize agents: {str(e)}"
            return False, error_msg
    
    def execute_workflow(self, progress_callback=None, log_callback=None):
        """Execute the complete workflow"""
        try:
            if not self.scheduler:
                raise Exception("Scheduler not initialized")
            
            results = {}
            
            # Step 1: Fetch Emails
            if log_callback:
                log_callback("step_start", "fetch_emails", "Fetch Emails")
                log_callback("agent_update", "Mail Fetcher", "🟡 Working")
            
            emails = self.scheduler.mail_fetcher.fetch_unread_emails()
            results['emails'] = emails
            results['total_emails'] = len(emails)
            
            if log_callback:
                log_callback("step_complete", "fetch_emails", "Fetch Emails")
                log_callback("agent_update", "Mail Fetcher", "✅ Ready")
                log_callback("info", f"📧 Fetched {len(emails)} emails")
            
            if progress_callback:
                progress_callback(15)
            
            # Step 2: Classify Emails
            if log_callback:
                log_callback("step_start", "classify_emails", "Classify Emails")
                log_callback("agent_update", "Classifier", "🟡 Working")
            
            support_emails = []
            for email in emails:
                if self.scheduler.classifier.classify_email(email):
                    support_emails.append(email)
            
            results['support_emails'] = support_emails
            
            if log_callback:
                log_callback("step_complete", "classify_emails", "Classify Emails")
                log_callback("agent_update", "Classifier", "✅ Ready")
                log_callback("info", f"🔍 Found {len(support_emails)} support emails")
            
            if progress_callback:
                progress_callback(30)
            
            # Step 3: Generate Summaries
            if log_callback:
                log_callback("step_start", "generate_summaries", "Generate Summaries")
                log_callback("agent_update", "Summary Agent", "🟡 Working")
            
            summaries = []
            for email in support_emails:
                summary = self.scheduler.summary.generate_summary(email)
                summaries.append(summary)
            
            results['summaries'] = summaries
            
            if log_callback:
                log_callback("step_complete", "generate_summaries", "Generate Summaries")
                log_callback("agent_update", "Summary Agent", "✅ Ready")
                log_callback("info", f"📝 Generated {len(summaries)} summaries")
            
            if progress_callback:
                progress_callback(45)
            
            # Step 4: Extract Categories
            if log_callback:
                log_callback("step_start", "extract_categories", "Extract Categories")
                log_callback("agent_update", "Category Extractor", "🟡 Working")
            
            categories = []
            for email in support_emails:
                category = self.scheduler.category_extractor.extract_category(email)
                categories.append(category)
            
            results['categories'] = categories
            
            if log_callback:
                log_callback("step_complete", "extract_categories", "Extract Categories")
                log_callback("agent_update", "Category Extractor", "✅ Ready")
                log_callback("info", f"🏷️ Extracted {len(categories)} categories")
            
            if progress_callback:
                progress_callback(60)
            
            # Step 5: Create ServiceNow Tickets
            if log_callback:
                log_callback("step_start", "create_tickets", "Create ServiceNow Tickets")
                log_callback("agent_update", "ServiceNow Agent", "🟡 Working")
            
            tickets_created = 0
            ticket_details = []
            
            for i, email in enumerate(support_emails):
                if i < len(summaries) and i < len(categories):
                    ticket_data = {
                        "email": email,
                        "summary": summaries[i],
                        "category": categories[i],
                        "short_description": summaries[i].get("short_description", "Support Request"),
                        "description": summaries[i].get("description", email.get("subject", "")),
                        "caller_email": email.get("from", ""),
                        "category_name": categories[i].get("category", "General"),
                        "priority": categories[i].get("priority", "3"),
                        "urgency": categories[i].get("urgency", "3")
                    }
                    
                    result = self.scheduler.servicenow.create_incident(ticket_data)
                    if result.get("success"):
                        tickets_created += 1
                        ticket_details.append({
                            "ticket_number": result.get("ticket_number"),
                            "sys_id": result.get("sys_id"),
                            "subject": email.get("subject", "No Subject"),
                            "caller": email.get("from", "")
                        })
            
            results['tickets_created'] = tickets_created
            results['ticket_details'] = ticket_details
            
            if log_callback:
                log_callback("step_complete", "create_tickets", "Create ServiceNow Tickets")
                log_callback("agent_update", "ServiceNow Agent", "✅ Ready")
                log_callback("info", f"🎫 Created {tickets_created} tickets")
            
            if progress_callback:
                progress_callback(75)
            
            # Step 6: Send Notifications
            if log_callback:
                log_callback("step_start", "send_notifications", "Send Notifications")
                log_callback("agent_update", "Notification Agent", "🟡 Working")
            
            notifications_sent = 0
            for i, email in enumerate(support_emails):
                if i < len(summaries) and i < len(ticket_details):
                    result = self.scheduler.notification.send_confirmation_email(
                        email.get("from", ""),
                        ticket_details[i]["ticket_number"],
                        summaries[i].get("short_description", "")
                    )
                    if result.get("success"):
                        notifications_sent += 1
            
            results['notifications_sent'] = notifications_sent
            
            if log_callback:
                log_callback("step_complete", "send_notifications", "Send Notifications")
                log_callback("agent_update", "Notification Agent", "✅ Ready")
                log_callback("info", f"📨 Sent {notifications_sent} notifications")
            
            if progress_callback:
                progress_callback(90)
            
            # Step 7: Start Tracking
            if log_callback:
                log_callback("step_start", "start_tracking", "Start Tracking")
                log_callback("agent_update", "Tracker Agent", "🟡 Working")
            
            tracking_started = 0
            for i, email in enumerate(support_emails):
                if i < len(ticket_details):
                    sys_id = ticket_details[i].get("sys_id", f"sys_id_{i}")
                    self.scheduler.tracker.start_tracking_ticket(
                        sys_id,
                        ticket_details[i]["ticket_number"],
                        email.get("from", "")
                    )
                    tracking_started += 1
            
            results['tracking_started'] = tracking_started
            
            if log_callback:
                log_callback("step_complete", "start_tracking", "Start Tracking")
                log_callback("agent_update", "Tracker Agent", "✅ Ready")
                log_callback("info", f"📊 Started tracking {tracking_started} tickets")
            
            if progress_callback:
                progress_callback(100)
            
            # Final results
            final_results = {
                'total_emails': len(emails),
                'support_emails': len(support_emails),
                'tickets_created': tickets_created,
                'notifications_sent': notifications_sent,
                'tracking_started': tracking_started,
                'ticket_details': ticket_details,
                'details': results
            }
            
            if log_callback:
                log_callback("workflow_complete", final_results)
            
            return final_results
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}\n{traceback.format_exc()}"
            if log_callback:
                log_callback("error", error_msg)
            raise e

# Global workflow manager
if 'workflow_manager' not in st.session_state:
    st.session_state.workflow_manager = WorkflowManager()

class StreamlitUI:
    def __init__(self):
        # Define workflow steps first
        self.workflow_steps = [
            {"id": "fetch_emails", "name": "Fetch Emails", "agent": "Mail Fetcher", "icon": "📧"},
            {"id": "classify_emails", "name": "Classify Emails", "agent": "Classifier", "icon": "🔍"},
            {"id": "generate_summaries", "name": "Generate Summaries", "agent": "Summary Agent", "icon": "📝"},
            {"id": "extract_categories", "name": "Extract Categories", "agent": "Category Extractor", "icon": "🏷️"},
            {"id": "create_tickets", "name": "Create ServiceNow Tickets", "agent": "ServiceNow Agent", "icon": "🎫"},
            {"id": "send_notifications", "name": "Send Notifications", "agent": "Notification Agent", "icon": "📨"},
            {"id": "start_tracking", "name": "Start Tracking", "agent": "Tracker Agent", "icon": "📊"}
        ]
        
        st.set_page_config(
            page_title="Agentic Workflow Dashboard",
            page_icon="🤖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS
        st.markdown("""
        <style>
        .agent-card {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            margin: 8px 0;
            border-left: 5px solid #6c757d;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .agent-card.success {
            border-left-color: #28a745;
            background-color: #f8fff9;
        }
        .agent-card.working {
            border-left-color: #ffc107;
            background-color: #fffbf0;
            animation: pulse 2s infinite;
        }
        .agent-card.error {
            border-left-color: #dc3545;
            background-color: #fff5f5;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        .step-indicator {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 8px 0;
            border-left: 4px solid #e9ecef;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .step-indicator.active {
            border-left-color: #ffc107;
            background-color: #fffbf0;
            animation: pulse 2s infinite;
        }
        .step-indicator.complete {
            border-left-color: #28a745;
            background-color: #f8fff9;
        }
        .metrics-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .workflow-header {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 12px;
            color: white;
            margin-bottom: 20px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Initialize session state properly
        self.init_session_state()
    
    def init_session_state(self):
        """Initialize session state variables"""
        # Workflow status
        if 'workflow_status' not in st.session_state:
            st.session_state.workflow_status = {
                'running': False,
                'current_step': None,
                'steps_completed': {},
                'last_run': None,
                'results': {},
                'progress': 0,
                'agents_initialized': False,
                'workflow_data': {},
                'logs': [],
                'error_logs': []
            }
        
        # Agent status
        if 'agent_status' not in st.session_state:
            st.session_state.agent_status = {
                'Mail Fetcher': {'status': '❓ Not Initialized', 'health': 'unknown', 'last_update': None},
                'Classifier': {'status': '❓ Not Initialized', 'health': 'unknown', 'last_update': None},
                'Summary Agent': {'status': '❓ Not Initialized', 'health': 'unknown', 'last_update': None},
                'Category Extractor': {'status': '❓ Not Initialized', 'health': 'unknown', 'last_update': None},
                'ServiceNow Agent': {'status': '❓ Not Initialized', 'health': 'unknown', 'last_update': None},
                'Notification Agent': {'status': '❓ Not Initialized', 'health': 'unknown', 'last_update': None},
                'Tracker Agent': {'status': '❓ Not Initialized', 'health': 'unknown', 'last_update': None}
            }
        
        # Initialize step status
        if 'workflow_steps_status' not in st.session_state:
            st.session_state.workflow_steps_status = {}
        
        for step in self.workflow_steps:
            if step['id'] not in st.session_state.workflow_steps_status:
                st.session_state.workflow_steps_status[step['id']] = False
    
    def add_log(self, message: str, log_type: str = "info"):
        """Add log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        if 'logs' not in st.session_state.workflow_status:
            st.session_state.workflow_status['logs'] = []
        if 'error_logs' not in st.session_state.workflow_status:
            st.session_state.workflow_status['error_logs'] = []
        
        if log_type == "error":
            st.session_state.workflow_status['error_logs'].append(log_entry)
        else:
            st.session_state.workflow_status['logs'].append(log_entry)
        
        # Keep only recent logs
        if len(st.session_state.workflow_status['logs']) > 100:
            st.session_state.workflow_status['logs'] = st.session_state.workflow_status['logs'][-100:]
        if len(st.session_state.workflow_status['error_logs']) > 50:
            st.session_state.workflow_status['error_logs'] = st.session_state.workflow_status['error_logs'][-50:]
    
    def update_agent_status(self, agent_name: str, status: str, health: str = None):
        """Update agent status"""
        if agent_name in st.session_state.agent_status:
            st.session_state.agent_status[agent_name]['status'] = status
            if health:
                st.session_state.agent_status[agent_name]['health'] = health
            st.session_state.agent_status[agent_name]['last_update'] = datetime.now().strftime("%H:%M:%S")
    
    def status_callback(self, message: str):
        """Callback for agent initialization status"""
        self.add_log(message)
        
        # Update agent status based on message
        for agent_name in st.session_state.agent_status.keys():
            if agent_name in message:
                if "Initializing" in message:
                    self.update_agent_status(agent_name, "🟡 Initializing", "initializing")
                elif "✅" in message and "initialized" in message:
                    self.update_agent_status(agent_name, "✅ Ready", "healthy")
                elif "❌" in message or "Failed" in message:
                    self.update_agent_status(agent_name, "❌ Error", "error")
    
    def initialize_agents(self):
        """Initialize agents with proper error handling"""
        with st.spinner("🚀 Initializing agents..."):
            try:
                # Update all agents to initializing status
                for agent_name in st.session_state.agent_status:
                    self.update_agent_status(agent_name, "🟡 Initializing", "initializing")
                
                success, message = st.session_state.workflow_manager.initialize_agents(
                    status_callback=self.status_callback
                )
                
                if success:
                    st.session_state.workflow_status['agents_initialized'] = True
                    st.success("✅ All agents initialized successfully!")
                else:
                    st.error(f"❌ Agent initialization failed: {message}")
                    self.add_log(f"Agent initialization failed: {message}", "error")
                    
                    # Mark failed agents
                    for agent_name in st.session_state.agent_status:
                        if st.session_state.agent_status[agent_name]['health'] == 'initializing':
                            self.update_agent_status(agent_name, "❌ Error", "error")
                
            except Exception as e:
                error_msg = f"Critical error during agent initialization: {str(e)}"
                st.error(error_msg)
                self.add_log(error_msg, "error")
                
                # Mark all agents as error
                for agent_name in st.session_state.agent_status:
                    self.update_agent_status(agent_name, "❌ Error", "error")
    
    def display_header(self):
        """Display dashboard header"""
        st.markdown("""
        <div class="workflow-header">
            <h1>🤖 Agentic Workflow Dashboard</h1>
            <p>Monitor and control the automated email-to-ticket workflow system</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Status indicators
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.session_state.workflow_status['running']:
                st.markdown("🟡 **Status:** Running")
            else:
                st.markdown("🟢 **Status:** Idle")
        
        with col2:
            healthy_agents = sum(1 for agent in st.session_state.agent_status.values() 
                               if agent['health'] == 'healthy')
            total_agents = len(st.session_state.agent_status)
            st.markdown(f"🤖 **Agents:** {healthy_agents}/{total_agents} Ready")
        
        with col3:
            if st.session_state.workflow_status['last_run']:
                st.markdown(f"⏰ **Last Run:** {st.session_state.workflow_status['last_run']}")
            else:
                st.markdown("⏰ **Last Run:** Never")
        
        with col4:
            if st.session_state.workflow_status['results']:
                tickets = st.session_state.workflow_status['results'].get('tickets_created', 0)
                st.markdown(f"🎫 **Tickets:** {tickets} Created")
            else:
                st.markdown("🎫 **Tickets:** 0 Created")
    
    def display_controls(self):
        """Display workflow controls"""
        st.subheader("🎛️ Workflow Controls")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            start_disabled = (st.session_state.workflow_status['running'] or 
                            not st.session_state.workflow_status['agents_initialized'])
            
            if st.button("▶️ Start Workflow", 
                        type="primary", 
                        disabled=start_disabled,
                        help="Start the complete email-to-ticket workflow",
                        use_container_width=True):
                self.start_workflow()
        
        with col2:
            if st.button("⏹️ Stop Workflow", 
                        disabled=not st.session_state.workflow_status['running'],
                        help="Stop the currently running workflow",
                        use_container_width=True):
                self.stop_workflow()
        
        with col3:
            if st.button("🔄 Reset Status", 
                        help="Reset workflow status and logs",
                        use_container_width=True):
                self.reset_workflow()
        
        with col4:
            if st.button("🔧 Initialize Agents",
                        disabled=st.session_state.workflow_status['running'],
                        help="Initialize or reinitialize all agents",
                        use_container_width=True):
                st.session_state.workflow_status['agents_initialized'] = False
                self.initialize_agents()
                st.rerun()
    
    def start_workflow(self):
        """Start workflow execution"""
        if not st.session_state.workflow_status['agents_initialized']:
            st.error("❌ Agents not initialized. Please initialize agents first.")
            return
        
        # Reset workflow state
        st.session_state.workflow_status['running'] = True
        st.session_state.workflow_status['progress'] = 0
        st.session_state.workflow_status['current_step'] = None
        st.session_state.workflow_status['results'] = {}
        
        # Reset step status
        for step in self.workflow_steps:
            st.session_state.workflow_steps_status[step['id']] = False
        
        # Clear logs
        st.session_state.workflow_status['logs'] = []
        st.session_state.workflow_status['error_logs'] = []
        
        self.add_log("🚀 Workflow execution started!")
        
        # Execute workflow
        self.execute_workflow_sync()
    
    def execute_workflow_sync(self):
        """Execute workflow synchronously with proper state management"""
        try:
            def progress_callback(progress):
                st.session_state.workflow_status['progress'] = progress
            
            def log_callback(log_type, *args):
                if log_type == "step_start":
                    step_id, step_name = args
                    st.session_state.workflow_status['current_step'] = step_id
                    self.add_log(f"🚀 Started: {step_name}")
                    
                elif log_type == "step_complete":
                    step_id, step_name = args
                    st.session_state.workflow_steps_status[step_id] = True
                    st.session_state.workflow_status['current_step'] = None
                    self.add_log(f"✅ Completed: {step_name}")
                    
                elif log_type == "agent_update":
                    agent_name, status = args
                    health = "working" if "Working" in status else "healthy" if "Ready" in status else "error"
                    self.update_agent_status(agent_name, status, health)
                    
                elif log_type == "info":
                    message = args[0]
                    self.add_log(message)
                    
                elif log_type == "error":
                    message = args[0]
                    self.add_log(message, "error")
                    st.session_state.workflow_status['running'] = False
                    
                elif log_type == "workflow_complete":
                    results = args[0]
                    st.session_state.workflow_status['running'] = False
                    st.session_state.workflow_status['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state.workflow_status['results'] = results
                    self.add_log("🎉 Workflow completed successfully!")
            
            # Execute the workflow
            results = st.session_state.workflow_manager.execute_workflow(
                progress_callback=progress_callback,
                log_callback=log_callback
            )
            
            st.success("✅ Workflow completed successfully!")
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            st.error(error_msg)
            self.add_log(error_msg, "error")
            st.session_state.workflow_status['running'] = False
            
            # Reset agent statuses
            for agent_name in st.session_state.agent_status:
                if st.session_state.agent_status[agent_name]['health'] == 'working':
                    self.update_agent_status(agent_name, "❌ Error", "error")
    
    def stop_workflow(self):
        """Stop workflow execution"""
        st.session_state.workflow_status['running'] = False
        st.session_state.workflow_status['current_step'] = None
        self.add_log("⏹️ Workflow stopped by user")
        st.info("🛑 Workflow stopped")
        st.rerun()
    
    def reset_workflow(self):
        """Reset all workflow status"""
        st.session_state.workflow_status = {
            'running': False,
            'current_step': None,
            'last_run': None,
            'results': {},
            'progress': 0,
            'agents_initialized': st.session_state.workflow_status.get('agents_initialized', False),
            'workflow_data': {},
            'logs': [],
            'error_logs': []
        }
        
        # Reset step status
        for step in self.workflow_steps:
            st.session_state.workflow_steps_status[step['id']] = False
        
        st.success("✅ Workflow status reset!")
        st.rerun()
    
    def display_agent_status_grid(self):
        """Display agents in a responsive grid"""
        st.subheader("🤖 Agent Status Monitor")
        
        # Create responsive grid
        cols = st.columns(3)  # 3 columns for better layout
        
        agent_list = list(st.session_state.agent_status.items())
        
        for i, (agent_name, agent_info) in enumerate(agent_list):
            with cols[i % 3]:
                status = agent_info['status']
                health = agent_info['health']
                last_update = agent_info.get('last_update', 'Never')
                
                # Determine card styling
                card_class = "agent-card"
                if health == 'healthy':
                    card_class += " success"
                elif health == 'working':
                    card_class += " working"
                elif health == 'error':
                    card_class += " error"
                
                # Get icon for agent
                icon = "🤖"
                for step in self.workflow_steps:
                    if step['agent'] == agent_name:
                        icon = step['icon']
                        break
                
                st.markdown(f"""
                <div class="{card_class}">
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <div style="font-size: 24px; margin-right: 10px;">{icon}</div>
                        <div>
                            <h4 style="margin: 0; color: #333;">{agent_name}</h4>
                            <small style="color: #666;">Last update: {last_update}</small>
                        </div>
                    </div>
                    <p style="margin: 0;"><strong>Status:</strong> {status}</p>
                </div>
                """, unsafe_allow_html=True)
    
    def display_workflow_progress(self):
        """Display detailed workflow progress"""
        st.subheader("📈 Workflow Progress")
        
        # Overall progress
        progress = st.session_state.workflow_status['progress']
        st.progress(progress / 100, text=f"Overall Progress: {progress:.0f}%")
        
        # Step indicators
        st.markdown("### 📋 Step Progress")
        
        for i, step in enumerate(self.workflow_steps):
            step_completed = st.session_state.workflow_steps_status.get(step['id'], False)
            is_current = st.session_state.workflow_status.get('current_step') == step['id']
            
            # Determine styling
            if step_completed:
                icon = "✅"
                step_class = "step-indicator complete"
                status_text = "Completed"
            elif is_current:
                icon = "🔄"
                step_class = "step-indicator active"
                status_text = "In Progress"
            else:
                icon = "⏳"
                step_class = "step-indicator"
                status_text = "Pending"
            
            col1, col2 = st.columns([1, 8])
            
            with col1:
                st.markdown(f"<div style='font-size: 32px; text-align: center; padding: 10px;'>{icon}</div>", 
                           unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="{step_class}">
                    <div style="display: flex; justify-content: between; align-items: center;">
                        <div>
                            <h5 style="margin: 0;">{step['icon']} {step['name']}</h5>
                            <p style="margin: 5px 0; color: #666;">Agent: {step['agent']}</p>
                        </div>
                        <div style="text-align: right;">
                            <strong>{status_text}</strong>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Add connector line except for last step
            if i < len(self.workflow_steps) - 1:
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    
    def display_metrics(self):
        """Display workflow metrics and results"""
        st.subheader("📊 Workflow Metrics")
        
        if st.session_state.workflow_status['results']:
            results = st.session_state.workflow_status['results']
            
            # Main metrics
            col1, col2, col3, col4 = st.columns(4)
            
            metrics = [
                ("📧", "Total Emails", results.get('total_emails', 0)),
                ("🎯", "Support Emails", results.get('support_emails', 0)),
                ("🎫", "Tickets Created", results.get('tickets_created', 0)),
                ("📨", "Notifications", results.get('notifications_sent', 0))
            ]
            
            for col, (icon, label, value) in zip([col1, col2, col3, col4], metrics):
                with col:
                    st.markdown(f"""
                    <div class="metrics-card">
                        <div style="font-size: 24px; margin-bottom: 10px;">{icon}</div>
                        <h2 style="margin: 0;">{value}</h2>
                        <p style="margin: 0; opacity: 0.9;">{label}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Detailed results
            st.markdown("### 📋 Ticket Details")
            
            if 'ticket_details' in results and results['ticket_details']:
                for i, ticket in enumerate(results['ticket_details']):
                    with st.container():
                        col1, col2, col3 = st.columns([2, 3, 2])
                        
                        with col1:
                            st.markdown(f"**🎫 Ticket #{i+1}**")
                            st.code(ticket.get('ticket_number', 'N/A'))
                        
                        with col2:
                            st.markdown("**📧 Subject**")
                            st.write(ticket.get('subject', 'No Subject'))
                        
                        with col3:
                            st.markdown("**👤 Caller**")
                            st.write(ticket.get('caller', 'Unknown'))
                        
                        st.divider()
            else:
                st.info("📄 No ticket details available")
                
        else:
            st.info("📊 No metrics available. Run the workflow to see results.")
    
    def display_logs(self):
        """Display system logs with filtering"""
        st.subheader("📋 System Logs")
        
        # Log controls
        col1, col2 = st.columns([3, 1])
        
        with col1:
            log_filter = st.selectbox("Filter logs:", ["All", "Info", "Errors Only"])
        
        with col2:
            if st.button("🗑️ Clear Logs", use_container_width=True):
                st.session_state.workflow_status['logs'] = []
                st.session_state.workflow_status['error_logs'] = []
                st.success("Logs cleared!")
                st.rerun()
        
        # Display error logs
        if st.session_state.workflow_status.get('error_logs') and log_filter in ["All", "Errors Only"]:
            st.markdown("### ❌ Error Logs")
            error_container = st.container()
            with error_container:
                for log in reversed(st.session_state.workflow_status['error_logs'][-10:]):
                    st.error(log)
        
        # Display info logs
        if st.session_state.workflow_status.get('logs') and log_filter in ["All", "Info"]:
            st.markdown("### ℹ️ Activity Logs")
            log_container = st.container()
            
            with log_container:
                if st.session_state.workflow_status['logs']:
                    # Show latest logs first
                    for log in reversed(st.session_state.workflow_status['logs'][-20:]):
                        st.text(log)
                else:
                    st.info("No activity logs yet.")
        
        # Live log updates
        if st.session_state.workflow_status['running']:
            st.markdown("### 🔴 Live Activity")
            if st.session_state.workflow_status['logs']:
                latest_log = st.session_state.workflow_status['logs'][-1]
                st.code(latest_log, language=None)
    
    def display_sidebar(self):
        """Display sidebar with controls and monitoring"""
        with st.sidebar:
            st.header("🔧 System Control")
            
            # System status
            st.subheader("📊 System Status")
            
            # Agent health overview
            healthy_agents = sum(1 for agent in st.session_state.agent_status.values() 
                               if agent['health'] == 'healthy')
            total_agents = len(st.session_state.agent_status)
            
            if total_agents > 0:
                health_percentage = (healthy_agents / total_agents) * 100
                
                if health_percentage == 100:
                    st.success(f"✅ All agents operational")
                elif health_percentage >= 70:
                    st.warning(f"⚠️ {healthy_agents}/{total_agents} agents ready")
                else:
                    st.error(f"❌ {healthy_agents}/{total_agents} agents ready")
                
                st.progress(health_percentage / 100)
            
            # Quick actions
            st.subheader("⚡ Quick Actions")
            
            if st.button("🔄 Refresh Dashboard", use_container_width=True):
                st.rerun()
            
            if st.button("🔧 Force Agent Restart", use_container_width=True):
                st.session_state.workflow_status['agents_initialized'] = False
                for agent_name in st.session_state.agent_status:
                    self.update_agent_status(agent_name, "❓ Not Initialized", "unknown")
                st.info("Agent restart initiated...")
                st.rerun()
            
            # Settings
            st.subheader("⚙️ Settings")
            
            auto_refresh = st.checkbox("Auto-refresh during workflow", value=True)
            refresh_interval = st.slider("Refresh interval (seconds)", 1, 10, 2)
            
            # System information
            st.subheader("ℹ️ System Info")
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.text(f"Time: {current_time}")
            st.text(f"Agents: {'✅ Ready' if st.session_state.workflow_status['agents_initialized'] else '❌ Not Ready'}")
            st.text(f"Workflow: {'🟡 Running' if st.session_state.workflow_status['running'] else '🟢 Idle'}")
            
            # Debug information
            with st.expander("🐛 Debug Info"):
                st.json({
                    "imports_successful": IMPORTS_SUCCESS,
                    "agents_initialized": st.session_state.workflow_status.get('agents_initialized', False),
                    "current_step": st.session_state.workflow_status.get('current_step'),
                    "progress": st.session_state.workflow_status.get('progress', 0),
                    "workflow_manager_exists": hasattr(st.session_state, 'workflow_manager')
                })
    
    def run(self):
        """Main UI execution method"""
        # Check import status
        if not IMPORTS_SUCCESS:
            st.error("❌ **Critical Error: Failed to import required modules**")
            st.markdown(f"**Import Error:** `{IMPORT_ERROR}`")
            
            with st.expander("🔧 Troubleshooting Guide"):
                st.markdown("""
                **Common Issues and Solutions:**
                
                1. **Missing Agent Files:**
                   - Ensure all files exist in `agents/` directory
                   - Check file permissions
                
                2. **Missing Dependencies:**
                   ```bash
                   pip install openai requests pyyaml python-dotenv
                   ```
                
                3. **Configuration Issues:**
                   - Verify `config/config.yaml` exists
                   - Check `.env` file with API keys
                   - Ensure `tools/config_loader.py` exists
                
                4. **Path Issues:**
                   - Run from project root directory
                   - Check Python path configuration
                """)
            return
        
        # Display sidebar
        self.display_sidebar()
        
        # Main header
        self.display_header()
        
        # Initialize agents if not done
        if not st.session_state.workflow_status.get('agents_initialized', False):
            st.warning("⚠️ Agents not initialized. Initializing now...")
            self.initialize_agents()
        
        # Main content tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🏠 Dashboard", "⚙️ Workflow", "🤖 Agents", "📋 Logs"])
        
        with tab1:
            # Controls section
            st.markdown("---")
            self.display_controls()
            
            # Main dashboard content
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.markdown("---")
                self.display_workflow_progress()
            
            with col_right:
                st.markdown("---")
                self.display_metrics()
        
        with tab2:
            st.subheader("🔄 Workflow Architecture")
            
            # Visual workflow diagram
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; border-radius: 15px; color: white; margin: 20px 0;">
                <h2 style="text-align: center; margin-bottom: 30px;">📧 ➜ 🤖 ➜ 🎫 Email-to-Ticket Pipeline</h2>
            """, unsafe_allow_html=True)
            
            # Create workflow steps visualization
            step_cols = st.columns(len(self.workflow_steps))
            
            for i, (col, step) in enumerate(zip(step_cols, self.workflow_steps)):
                with col:
                    step_completed = st.session_state.workflow_steps_status.get(step['id'], False)
                    is_current = st.session_state.workflow_status.get('current_step') == step['id']
                    
                    if step_completed:
                        color = "#28a745"
                        status = "✅ Done"
                    elif is_current:
                        color = "#ffc107"
                        status = "🔄 Active"
                    else:
                        color = "#6c757d"
                        status = "⏳ Waiting"
                    
                    st.markdown(f"""
                    <div style="text-align: center; color: white; padding: 10px;">
                        <div style="background-color: {color}; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px auto; font-size: 20px;">
                            {step['icon']}
                        </div>
                        <h6 style="margin: 5px 0; font-weight: bold;">{step['name']}</h6>
                        <small>{status}</small>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Current workflow data
            if st.session_state.workflow_status.get('results'):
                st.subheader("📊 Current Run Data")
                results = st.session_state.workflow_status['results']
                
                # Summary metrics
                metric_cols = st.columns(4)
                metrics_data = [
                    ("📧 Emails Processed", results.get('total_emails', 0)),
                    ("🎯 Support Cases", results.get('support_emails', 0)),
                    ("🎫 Tickets Created", results.get('tickets_created', 0)),
                    ("📨 Notifications Sent", results.get('notifications_sent', 0))
                ]
                
                for col, (label, value) in zip(metric_cols, metrics_data):
                    with col:
                        st.metric(label, value)
                
                # Detailed breakdown
                if 'ticket_details' in results and results['ticket_details']:
                    with st.expander("🎫 Created Tickets Details", expanded=False):
                        for i, ticket in enumerate(results['ticket_details'][:10]):  # Show max 10
                            st.markdown(f"""
                            **Ticket {i+1}:** `{ticket.get('ticket_number', 'N/A')}`  
                            **Subject:** {ticket.get('subject', 'No Subject')}  
                            **From:** {ticket.get('caller', 'Unknown')}
                            """)
                            if i < len(results['ticket_details']) - 1:
                                st.divider()
            else:
                st.info("📋 No workflow data available yet. Start a workflow to see results.")
        
        with tab3:
            self.display_agent_status_grid()
            
            st.markdown("---")
            st.subheader("🔧 Agent Configuration & Health")
            
            # Agent details with health checks
            for agent_name, agent_info in st.session_state.agent_status.items():
                with st.expander(f"{agent_name} - {agent_info['status']}", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Current Status:**")
                        st.write(agent_info['status'])
                        st.markdown("**Health:**")
                        st.write(agent_info['health'])
                        st.markdown("**Last Update:**")
                        st.write(agent_info.get('last_update', 'Never'))
                    
                    with col2:
                        st.markdown("**Configuration:**")
                        
                        # Agent-specific configuration info
                        agent_configs = {
                            'Mail Fetcher': {'type': 'Gmail IMAP', 'protocol': 'IMAP over SSL'},
                            'Classifier': {'type': 'AI Classification', 'model': 'OpenAI GPT-4'},
                            'Summary Agent': {'type': 'AI Summarization', 'model': 'OpenAI GPT-4'},
                            'Category Extractor': {'type': 'AI Categorization', 'model': 'OpenAI GPT-4'},
                            'ServiceNow Agent': {'type': 'REST API Client', 'endpoint': 'ServiceNow'},
                            'Notification Agent': {'type': 'SMTP Client', 'protocol': 'Email'},
                            'Tracker Agent': {'type': 'Background Monitor', 'method': 'Polling'}
                        }
                        
                        config = agent_configs.get(agent_name, {'type': 'Unknown', 'protocol': 'N/A'})
                        st.write(f"Type: {config['type']}")
                        st.write(f"Protocol: {config.get('protocol', config.get('model', config.get('method', 'N/A')))}")
                        
                        # Health check button
                        if agent_info['health'] == 'error':
                            if st.button(f"🔄 Restart {agent_name}", key=f"restart_{agent_name.replace(' ', '_')}"):
                                st.info(f"Attempting to restart {agent_name}...")
                                # Reset agent status
                                self.update_agent_status(agent_name, "🟡 Restarting", "initializing")
                                st.rerun()
        
        with tab4:
            self.display_logs()
        
        # Auto-refresh logic for running workflows
        if (st.session_state.workflow_status.get('running', False) and 
            st.sidebar.checkbox("Auto-refresh", value=True)):
            
            time.sleep(2)
            st.rerun()
        
        # Footer status
        self.display_footer_status()
    
    def display_footer_status(self):
        """Display footer with current status"""
        st.markdown("---")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            status = "🟡 Running" if st.session_state.workflow_status.get('running') else "🟢 Idle"
            st.markdown(f"**System:** {status}")
        
        with col2:
            current_step = st.session_state.workflow_status.get('current_step')
            if current_step:
                step_name = next((s['name'] for s in self.workflow_steps if s['id'] == current_step), 
                               current_step)
                st.markdown(f"**Current:** {step_name}")
            else:
                st.markdown("**Current:** No active step")
        
        with col3:
            progress = st.session_state.workflow_status.get('progress', 0)
            st.markdown(f"**Progress:** {progress:.0f}%")
        
        with col4:
            healthy_agents = sum(1 for agent in st.session_state.agent_status.values() 
                               if agent['health'] == 'healthy')
            total_agents = len(st.session_state.agent_status)
            st.markdown(f"**Agents:** {healthy_agents}/{total_agents}")

def main():
    """Main function with proper error handling"""
    try:
        ui = StreamlitUI()
        ui.run()
        
    except Exception as e:
        st.error("❌ **Critical Application Error**")
        
        # Error details
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("**Error Details:**")
            st.code(str(e))
            
            with st.expander("🔍 Full Traceback"):
                st.code(traceback.format_exc())
        
        with col2:
            st.markdown("**Quick Fixes:**")
            st.markdown("""
            1. 🔄 Refresh the page
            2. 🔧 Check agent files exist
            3. 📦 Install dependencies
            4. 🔑 Verify configuration
            5. 📁 Run from correct directory
            """)
            
            if st.button("🔄 Retry Application", use_container_width=True):
                st.rerun()

# Application entry point
if __name__ == "__main__":
    main()