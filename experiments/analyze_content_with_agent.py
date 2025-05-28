import os

from ai.asentrx_agent import ContentAnalyzer
from utils.logger_config import configure_logging

try:
    configure_logging()
except ValueError:
    pass


content = os.getenv("TEMP_TEST_CONTENT")
content_analyzer = ContentAnalyzer()
result = content_analyzer.analyze_content(content)
print(result)