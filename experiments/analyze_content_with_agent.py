from ai.asentrx_agent import ContentAnalyzer
from utils.logger_config import configure_logging

try:
    configure_logging()
except ValueError: # Handle potential issue if already configured by another entry point
    pass


content_cleaned = "We will sell all our gold and buy bitcoin instead."
content_analyzer = ContentAnalyzer()
content_analyzer.analyze_content(content_cleaned)