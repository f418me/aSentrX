from ai.asentrx_agent import ContentAnalyzer
from utils.logger_config import configure_logging

try:
    configure_logging()
except ValueError: # Handle potential issue if already configured by another entry point
    pass


#content_cleaned = "We will sell all our gold and buy bitcoin instead."
content_cleaned = "The EU will have to pay 50% import tarfis from now."
content_analyzer = ContentAnalyzer()
result = content_analyzer.analyze_content(content_cleaned)
print(result)