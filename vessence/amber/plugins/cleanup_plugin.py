# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import logging
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext

logger = logging.getLogger('google_adk.image_cleanup_plugin')

class ImageCleanupPlugin(BasePlugin):
    """A plugin that removes images from the session history after each turn to save context space."""

    def __init__(self):
        super().__init__(name="image_cleanup")

    async def after_run_callback(self, *, invocation_context: InvocationContext) -> None:
        """Executed after the final response is delivered. Cleans up stale images."""
        cleaned_count = 0
        
        for event in invocation_context.session.events:
            if not event.content or not event.content.parts:
                continue
            
            new_parts = []
            for part in event.content.parts:
                # Check if this part contains inline image data
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    # Replace with a placeholder to inform the model the image was there but is now cleared
                    from google.genai import types
                    new_parts.append(types.Part(text=f"[Screenshot removed from context to save space: {part.inline_data.mime_type}]"))
                    cleaned_count += 1
                else:
                    new_parts.append(part)
            
            event.content.parts = new_parts
            
        if cleaned_count > 0:
            logger.info(f"ImageCleanupPlugin: Cleared {cleaned_count} images from session history.")
