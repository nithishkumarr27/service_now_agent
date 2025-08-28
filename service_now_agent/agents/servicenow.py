"""
ServiceNow Agent - Creates incidents in ServiceNow using REST API
Handles dynamic user/group lookups with fallback to config defaults
"""

import logging
from typing import Dict, Any, Optional,List
import httpx
import json
from datetime import datetime

from tools.servicenow_api import ServiceNowAPI
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ServiceNowAgent:
    """Agent responsible for creating and managing ServiceNow incidents"""
    
    def __init__(self, config):
        self.config = config
        
        # Initialize ServiceNow API helper
        self.servicenow_api = ServiceNowAPI(config)
        
        # Cache for user and group lookups
        self._user_cache = {}
        self._group_cache = {}
        self._category_cache = {}
        
        # Get fallback assignments from config
        self.fallback_config = config.get_setting("servicenow_fallbacks", {})
    
    def create_incident(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an incident in ServiceNow
        
        Args:
            ticket_data: Dictionary containing ticket information
            
        Returns:
            Dict containing creation result with ticket number and sys_id
        """
        try:
            email_data = ticket_data.get("email", {})
            summary_data = ticket_data.get("summary", {})
            category_data = ticket_data.get("category", {})
            
            logger.info(f"Creating ServiceNow incident for {email_data.get('from', 'unknown')}")
            
            # Lookup caller information
            caller_info = self._lookup_caller(email_data.get("from", ""))
            
            # Lookup assignment group
            assignment_group = self._lookup_assignment_group(category_data.get("category", "General"))
            
            # Lookup assigned user
            assigned_user = self._lookup_assigned_user(category_data.get("category", "General"))
            
            # Prepare incident data
            incident_data = {
                "short_description": ticket_data.get("short_description", "Support Request")[:160],
                "description": self._build_incident_description(ticket_data),
                "caller_id": caller_info.get("sys_id", ""),
                "category": self._map_category_to_servicenow(category_data.get("category", "General")),
                "subcategory": category_data.get("subcategory", ""),
                "priority": category_data.get("priority", "3"),
                "urgency": category_data.get("urgency", "3"),
                "assignment_group": assignment_group.get("sys_id", ""),
                "assigned_to": assigned_user.get("sys_id", ""),
                "contact_type": "Email",
                "u_source_email": email_data.get("from", ""),
                "u_email_subject": email_data.get("subject", "")[:255],
                "comments": f"Auto-generated from email: {email_data.get('message_id', '')}"
            }
            
            # Create incident via API
            # Create incident via API
            result = self.servicenow_api.create_incident(incident_data)
            logger.debug(f"ServiceNow API response: {result}")  # Add this line
            if result.get("success"):
                logger.info(f"Successfully created incident: {result.get('ticket_number')}")
                return {
                    "success": True,
                    "ticket_number": result.get("ticket_number"),
                    "sys_id": result.get("sys_id"),
                    "assignment_group": assignment_group.get("name", ""),
                    "assigned_user": assigned_user.get("name", ""),
                    "caller": caller_info.get("name", "")
                }
            else:
                # Handle both string and dictionary error messages
                error_msg = result.get("error", "Unknown error")
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                else:
                    error_msg = str(error_msg)
                
                logger.error(f"Failed to create incident: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Error creating ServiceNow incident: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_incident_description(self, ticket_data: Dict[str, Any]) -> str:
        """Build detailed incident description"""
        email_data = ticket_data.get("email", {})
        summary_data = ticket_data.get("summary", {})
        category_data = ticket_data.get("category", {})
        
        description_parts = []
        
        # Add summary description
        if summary_data.get("description"):
            description_parts.append("Issue Description:")
            description_parts.append(summary_data["description"])
            description_parts.append("")
        
        # Add email details
        description_parts.append("Email Details:")
        description_parts.append(f"From: {email_data.get('from', 'Unknown')}")
        description_parts.append(f"Subject: {email_data.get('subject', 'No Subject')}")
        description_parts.append(f"Date: {email_data.get('date', 'Unknown')}")
        
        # Add body preview if available
        if email_data.get("body_preview"):
            description_parts.append("")
            description_parts.append("Email Preview:")
            description_parts.append(email_data["body_preview"])
        
        # Add categorization info
        if category_data.get("reasoning"):
            description_parts.append("")
            description_parts.append("Categorization:")
            description_parts.append(f"Category: {category_data.get('category', 'General')}")
            description_parts.append(f"Reasoning: {category_data.get('reasoning', '')}")
        
        # Add timestamp
        description_parts.append("")
        description_parts.append(f"Auto-generated: {datetime.now().isoformat()}")
        
        return "\n".join(description_parts)
    
    def _lookup_caller(self, email_address: str) -> Dict[str, Any]:
        """Lookup caller information by email address"""
        if not email_address:
            return self._get_fallback_caller()
        
        # Check cache first
        if email_address in self._user_cache:
            return self._user_cache[email_address]
        
        try:
            # Lookup user in ServiceNow
            user_result = self.servicenow_api.lookup_user_by_email(email_address)
            
            if user_result.get("found"):
                caller_info = {
                    "sys_id": user_result.get("sys_id"),
                    "name": user_result.get("name"),
                    "email": email_address
                }
                # Cache result
                self._user_cache[email_address] = caller_info
                logger.debug(f"Found caller: {caller_info['name']}")
                return caller_info
            else:
                # Create new user or use fallback
                return self._handle_unknown_caller(email_address)
                
        except Exception as e:
            logger.error(f"Error looking up caller {email_address}: {e}")
            return self._get_fallback_caller()
    
    def _handle_unknown_caller(self, email_address: str) -> Dict[str, Any]:
        """Handle unknown caller - create user or use fallback"""
        try:
            # Try to create new user
            if self.config.get_setting("create_unknown_users", False):
                user_data = {
                    "email": email_address,
                    "user_name": email_address.split("@")[0],
                    "first_name": email_address.split("@")[0],
                    "last_name": "External",
                    "active": True
                }
                
                result = self.servicenow_api.create_user(user_data)
                if result.get("success"):
                    caller_info = {
                        "sys_id": result.get("sys_id"),
                        "name": result.get("name"),
                        "email": email_address
                    }
                    self._user_cache[email_address] = caller_info
                    logger.info(f"Created new user: {email_address}")
                    return caller_info
            
            # Fallback to default caller
            return self._get_fallback_caller()
            
        except Exception as e:
            logger.error(f"Error handling unknown caller: {e}")
            return self._get_fallback_caller()
    
    def _get_fallback_caller(self) -> Dict[str, Any]:
        """Get fallback caller from config"""
        fallback_user = self.fallback_config.get("default_caller", {})
        
        if not fallback_user:
            # Hardcoded fallback
            return {
                "sys_id": "",
                "name": "Unknown Caller",
                "email": "unknown@company.com"
            }
        
        return {
            "sys_id": fallback_user.get("sys_id", ""),
            "name": fallback_user.get("name", "Default Caller"),
            "email": fallback_user.get("email", "default@company.com")
        }
    
    def _lookup_assignment_group(self, category: str) -> Dict[str, Any]:
        """Lookup assignment group based on category"""
        cache_key = f"group_{category}"
        
        # Check cache
        if cache_key in self._group_cache:
            return self._group_cache[cache_key]
        
        try:
            # Get group mapping from config
            group_mappings = self.config.get_setting("category_to_group", {})
            mapped_group = group_mappings.get(category)
            
            if mapped_group:
                # Lookup group in ServiceNow
                result = self.servicenow_api.lookup_group_by_name(mapped_group)
                
                if result.get("found"):
                    group_info = {
                        "sys_id": result.get("sys_id"),
                        "name": result.get("name")
                    }
                    self._group_cache[cache_key] = group_info
                    return group_info
            
            # Fallback to default group
            return self._get_fallback_group()
            
        except Exception as e:
            logger.error(f"Error looking up assignment group for {category}: {e}")
            return self._get_fallback_group()
    
    def _get_fallback_group(self) -> Dict[str, Any]:
        """Get fallback assignment group from config"""
        fallback_group = self.fallback_config.get("default_assignment_group", {})
        
        if not fallback_group:
            return {
                "sys_id": "",
                "name": "General Support"
            }
        
        return {
            "sys_id": fallback_group.get("sys_id", ""),
            "name": fallback_group.get("name", "Default Group")
        }
    
    def _lookup_assigned_user(self, category: str) -> Dict[str, Any]:
        """Lookup assigned user based on category"""
        cache_key = f"user_{category}"
        
        # Check cache
        if cache_key in self._user_cache:
            return self._user_cache[cache_key]
        
        try:
            # Get user mapping from config
            user_mappings = self.config.get_setting("category_to_user", {})
            mapped_user = user_mappings.get(category)
            
            if mapped_user:
                # Lookup user in ServiceNow
                result = self.servicenow_api.lookup_user_by_username(mapped_user)
                
                if result.get("found"):
                    user_info = {
                        "sys_id": result.get("sys_id"),
                        "name": result.get("name")
                    }
                    self._user_cache[cache_key] = user_info
                    return user_info
            
            # No specific user assignment
            return {"sys_id": "", "name": ""}
            
        except Exception as e:
            logger.error(f"Error looking up assigned user for {category}: {e}")
            return {"sys_id": "", "name": ""}
    
    def _map_category_to_servicenow(self, category: str) -> str:
        """Map internal category to ServiceNow category values"""
        category_mappings = self.config.get_setting("servicenow_category_mapping", {})
        
        # Use mapping if available
        if category in category_mappings:
            return category_mappings[category]
        
        # Default mappings
        default_mappings = {
            "IT": "Software",
            "HR": "Human Resources",
            "Finance": "Finance",
            "Facilities": "Facilities",
            "General": "General"
        }
        
        return default_mappings.get(category, "General")
    
    def update_incident(self, sys_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing incident in ServiceNow"""
        try:
            result = self.servicenow_api.update_incident(sys_id, update_data)
            
            if result.get("success"):
                logger.info(f"Successfully updated incident {sys_id}")
                return {"success": True}
            else:
                logger.error(f"Failed to update incident {sys_id}: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
                
        except Exception as e:
            logger.error(f"Error updating incident {sys_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_incident_status(self, sys_id: str) -> Dict[str, Any]:
        """Get current status of incident"""
        try:
            result = self.servicenow_api.get_incident(sys_id)
            
            if result.get("found"):
                return {
                    "found": True,
                    "state": result.get("state"),
                    "state_name": result.get("state_name"),
                    "resolution_code": result.get("resolution_code"),
                    "resolution_notes": result.get("resolution_notes"),
                    "updated": result.get("sys_updated_on")
                }
            else:
                return {"found": False}
                
        except Exception as e:
            logger.error(f"Error getting incident status {sys_id}: {e}")
            return {"found": False, "error": str(e)}
    
    def add_comment_to_incident(self, sys_id: str, comment: str, comment_type: str = "work_notes") -> Dict[str, Any]:
        """Add comment/work note to incident"""
        try:
            result = self.servicenow_api.add_comment(sys_id, comment, comment_type)
            
            if result.get("success"):
                logger.debug(f"Added comment to incident {sys_id}")
                return {"success": True}
            else:
                logger.error(f"Failed to add comment to {sys_id}: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
                
        except Exception as e:
            logger.error(f"Error adding comment to {sys_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def close_incident(self, sys_id: str, resolution_code: str = "Closed/Resolved by Caller", 
                      resolution_notes: str = "") -> Dict[str, Any]:
        """Close an incident"""
        try:
            close_data = {
                "state": "6",  # Closed
                "resolution_code": resolution_code,
                "resolution_notes": resolution_notes,
                "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            result = self.servicenow_api.update_incident(sys_id, close_data)
            
            if result.get("success"):
                logger.info(f"Successfully closed incident {sys_id}")
                return {"success": True}
            else:
                logger.error(f"Failed to close incident {sys_id}: {result.get('error')}")
                return {"success": False, "error": result.get("error")}
                
        except Exception as e:
            logger.error(f"Error closing incident {sys_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def search_incidents_by_email(self, email: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """Search for recent incidents by caller email"""
        try:
            result = self.servicenow_api.search_incidents_by_caller_email(email, days_back)
            
            if result.get("success"):
                incidents = result.get("incidents", [])
                logger.debug(f"Found {len(incidents)} incidents for {email}")
                return incidents
            else:
                logger.error(f"Failed to search incidents for {email}: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching incidents for {email}: {e}")
            return []
    
    def get_incident_metrics(self) -> Dict[str, Any]:
        """Get incident metrics and statistics"""
        try:
            # This could be expanded to get various metrics
            metrics = {
                "total_created_today": 0,
                "open_incidents": 0,
                "avg_resolution_time": 0
            }
            
            # Implement actual metrics gathering if needed
            logger.debug("Retrieved incident metrics")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting incident metrics: {e}")
            return {}
    
    def validate_servicenow_connection(self) -> bool:
        """Validate connection to ServiceNow instance"""
        try:
            return self.servicenow_api.test_connection()
        except Exception as e:
            logger.error(f"ServiceNow connection validation failed: {e}")
            return False