import logging
import os
from typing import Union, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext  # RunContext might not be needed if tool is removed or simplified
from utils.logger_config import APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.asentrx_agent")

logger.debug("aSentrX Agent script (module) loaded or started.")

load_dotenv()

# --- Pydantic Models ---

class TopicClassification(BaseModel):
    """Result of the first agent, classifying the topic."""
    classification: str  # Expected: "market", "bitcoin", "tariffs", "others"
    confidence: float
    reasoning: str

class PriceDirectionPrediction(BaseModel):
    """Predicts the likely direction of price change for a specific topic."""
    direction: str  # Expected: "up", "down", "neutral"
    confidence: float
    reasoning: str

class Failed(BaseModel):
    """Unable to find a satisfactory choice for the current task."""

class AnalysisOutput(BaseModel):
    """
    Represents the final output of the ContentAnalyzer pipeline.
    Fields will be None if a corresponding step was not executed or did not produce a valid result.
    """
    topic_classification: Optional[str] = None
    topic_confidence: Optional[float] = None
    topic_reasoning: Optional[str] = None
    price_direction: Optional[str] = None
    price_confidence: Optional[float] = None
    price_reasoning: Optional[str] = None


# --- Agent Definitions ---

# Agent 1: Topic Classification
topic_classification_agent = Agent[None, Union[TopicClassification, Failed]](
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    output_type=Union[TopicClassification, Failed],
    system_prompt=(
        'Classify this tweet from the President of the USA into one of the following categories: '
        '"market", "bitcoin", "tariffs", or "others".\n'
        'Definitions:\n'
        '- market: General financial market news, economic indicators, or company news not specifically related to Bitcoin or tariffs.\n'
        '- bitcoin: Anything directly mentioning or clearly impacting Bitcoin or cryptocurrencies.\n'
        '- tariffs: News related to import/export duties, trade agreements, or taxes on goods/services between nations or for specific companies.\n'
        '- others: All other topics (e.g., private matters, general politics, non-economic announcements).\n'
        'Provide the `classification`, a `confidence` level (float 0.0-1.0), and a brief `reasoning`.'
    ),
)

# Optional: Tool for Agent 1 if special context is still needed for general topic classification
# If not, this tool can be removed or simplified.
@topic_classification_agent.tool
async def provide_context_for_topic_classification(ctx: RunContext[str]) -> str:
    logger.debug(f"Tool 'provide_context_for_topic_classification' called with deps: {ctx.deps}")
    # Example: You might provide a list of current hot economic topics or specific keywords to watch for.
    # For simplicity, we can keep the existing SPECIAL_CONTEXT or make it more generic.
    return f"Context hint: {os.getenv("SPECIAL_CONTEXT", "Focus on economic and financial implications.")}"


# Agent 2: Market Price Direction (for "market" classification)
market_price_direction_agent = Agent[None, Union[PriceDirectionPrediction, Failed]](
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    output_type=Union[PriceDirectionPrediction, Failed],
    system_prompt=(
        'This tweet from the President of the USA has been classified as "market" related. '
        'Based on its content:\n'
        '1. Predict whether the general market sentiment or relevant asset prices are more likely to go "up", "down", or remain "neutral". '
        '   Set this to `direction`.\n'
        '2. Provide a `confidence` level (float 0.0-1.0).\n'
        '3. Provide a brief `reasoning`.'
    ),
)

# Agent 3: Bitcoin Price Direction (for "bitcoin" classification)
bitcoin_price_direction_agent = Agent[None, Union[PriceDirectionPrediction, Failed]](
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    output_type=Union[PriceDirectionPrediction, Failed],
    system_prompt=(
        'This tweet from the President of the USA has been classified as "bitcoin" related. '
        'Based on its content:\n'
        '1. Predict whether the Bitcoin price is more likely to go "up", "down", or remain "neutral". '
        '   Set this to `direction`.\n'
        '2. Provide a `confidence` level (float 0.0-1.0).\n'
        '3. Provide a brief `reasoning`.'
    ),
)

# Agent 4: Tariffs Impact Direction (for "tariffs" classification)
tariffs_impact_direction_agent = Agent[None, Union[PriceDirectionPrediction, Failed]](
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    output_type=Union[PriceDirectionPrediction, Failed],
    system_prompt=(
        'This tweet from the President of the USA has been classified as "tariffs" related. '
        'Based on its content:\n'
        '1. Predict the likely impact direction on affected markets or the general economy. Use "up" if the impact is generally positive/easing (e.g., tariffs lowered), '
        '"down" if generally negative/constricting (e.g., tariffs increased or new ones imposed), or "neutral". '
        '   Set this to `direction`.\n'
        '   Consider: Higher tariffs/new duties usually mean "down" for overall trade/importer costs. Lowered tariffs/duties usually mean "up".\n'
        '2. Provide a `confidence` level (float 0.0-1.0).\n'
        '3. Provide a brief `reasoning`.'
    ),
)


class ContentAnalyzer:
    def __init__(self):
        logger.info("Initializing ContentAnalyzer...")

    def analyze_content(self, content: str, status_id_for_logging: str = "N/A") -> AnalysisOutput:
        """
        Analyzes content using a multi-step agent pipeline.
        1. Classifies the topic.
        2. Based on classification, runs a specific agent for price/impact direction.
        Returns an AnalysisOutput object.
        """
        logger.info(f"Status ID [{status_id_for_logging}]: Starting content analysis pipeline for: '{content[:100]}...'")
        pipeline_output = AnalysisOutput()

        try:
            # --- Step 1: Topic Classification ---
            logger.info(f"Status ID [{status_id_for_logging}]: Running topic classification agent...")
            # Pass a simple string or a more structured input if the tool expects it.
            # For now, assuming "General Knowledge" or similar default if tool not crucial.
            result_topic_classification = topic_classification_agent.run_sync(content, deps="Initial Analysis")


            if isinstance(result_topic_classification.output, Failed):
                logger.warning(
                    f"Status ID [{status_id_for_logging}]: Topic classification agent failed. Result: {result_topic_classification.output}")
                pipeline_output.topic_reasoning = "Topic classification agent failed."
                return pipeline_output # Early exit if primary classification fails

            elif isinstance(result_topic_classification.output, TopicClassification):
                topic_data = result_topic_classification.output
                pipeline_output.topic_classification = topic_data.classification
                pipeline_output.topic_confidence = topic_data.confidence
                pipeline_output.topic_reasoning = topic_data.reasoning
                logger.info(
                    f"Status ID [{status_id_for_logging}]: Topic classification result: "
                    f"Class='{topic_data.classification}', Confidence={topic_data.confidence:.2f}, "
                    f"Reasoning='{topic_data.reasoning}'"
                )

                # --- Step 2: Specific Agent based on Classification ---
                direction_agent_output = None
                agent_name_for_log = ""

                if topic_data.classification == "market":
                    agent_name_for_log = "Market Price Direction"
                    logger.info(f"Status ID [{status_id_for_logging}]: Running {agent_name_for_log} agent...")
                    result_market_direction = market_price_direction_agent.run_sync(content)
                    direction_agent_output = result_market_direction.output

                elif topic_data.classification == "bitcoin":
                    agent_name_for_log = "Bitcoin Price Direction"
                    logger.info(f"Status ID [{status_id_for_logging}]: Running {agent_name_for_log} agent...")
                    result_bitcoin_direction = bitcoin_price_direction_agent.run_sync(content)
                    direction_agent_output = result_bitcoin_direction.output

                elif topic_data.classification == "tariffs":
                    agent_name_for_log = "Tariffs Impact Direction"
                    logger.info(f"Status ID [{status_id_for_logging}]: Running {agent_name_for_log} agent...")
                    result_tariffs_direction = tariffs_impact_direction_agent.run_sync(content)
                    direction_agent_output = result_tariffs_direction.output

                elif topic_data.classification == "others":
                    logger.info(f"Status ID [{status_id_for_logging}]: Topic classified as 'others'. No further price direction analysis.")
                    # No specific agent to run, pipeline_output already has None for price fields.
                else:
                    logger.warning(
                        f"Status ID [{status_id_for_logging}]: Unknown topic classification '{topic_data.classification}'. Skipping direction agent.")

                # Process output of the specific direction agent
                if direction_agent_output:
                    if isinstance(direction_agent_output, Failed):
                        logger.warning(
                            f"Status ID [{status_id_for_logging}]: {agent_name_for_log} agent failed. Result: {direction_agent_output}")
                        pipeline_output.price_reasoning = f"{agent_name_for_log} agent failed."
                    elif isinstance(direction_agent_output, PriceDirectionPrediction):
                        pipeline_output.price_direction = direction_agent_output.direction
                        pipeline_output.price_confidence = direction_agent_output.confidence
                        pipeline_output.price_reasoning = direction_agent_output.reasoning
                        logger.info(
                            f"Status ID [{status_id_for_logging}]: {agent_name_for_log} result: "
                            f"Direction='{direction_agent_output.direction}', Confidence={direction_agent_output.confidence:.2f}, "
                            f"Reasoning='{direction_agent_output.reasoning}'"
                        )
                    else:
                        logger.error(
                            f"Status ID [{status_id_for_logging}]: {agent_name_for_log} agent returned an unexpected Pydantic model type: {type(direction_agent_output)}")
                        pipeline_output.price_reasoning = f"{agent_name_for_log} agent returned unexpected type."

            else: # Should not happen if Pydantic types are correctly handled by Agent
                logger.error(
                    f"Status ID [{status_id_for_logging}]: Topic classification agent returned an unexpected Pydantic model type: {type(result_topic_classification.output)}")
                pipeline_output.topic_reasoning = "Topic classification agent returned unexpected type."

        except Exception as e:
            logger.error(
                f"Status ID [{status_id_for_logging}]: An unexpected error occurred during content analysis pipeline: {e}",
                exc_info=True)
            # Ensure pipeline_output reflects a general failure if not already set
            if not pipeline_output.topic_reasoning and not pipeline_output.price_reasoning:
                 pipeline_output.topic_reasoning = f"Pipeline error: {e}"


        logger.info(f"Status ID [{status_id_for_logging}]: Content analysis pipeline finished.")
        return pipeline_output