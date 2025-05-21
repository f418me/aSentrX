import logging
import os
from typing import Union

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from utils.logger_config import configure_logging, APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.asentrx_agent")

logger.info("aSentrX Agent script (module) loaded or started.")

class FirstClassification(BaseModel):
    classification: str
    confidence: float
    reasoning: str  # ADDED: Reasoning for the classification


class BitcoinClassification(BaseModel):
    bitcoin_impact: bool
    confidence: float
    reasoning: str  # ADDED: Reasoning for the Bitcoin impact assessment


class BitcoinPriceDirection(BaseModel):
    """Predicts the likely direction of Bitcoin price change based on a tweet."""
    direction: str  # Expected: "up", "down", or "neutral"
    confidence: float
    reasoning: str  # Explanation for the predicted direction (already existed)

class Failed(BaseModel):
    """Unable to find a satisfactory choice for the current task."""

load_dotenv()

logger.info("Initializing FirstClassificationAgent...")
first_classification_agent = Agent[None, Union[FirstClassification, Failed]](
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    output_type=Union[FirstClassification, Failed],  # type: ignore
    system_prompt=(
        'Decide if this tweet from the President of the USA is from the class market, private or others. '
        'market: everything related to financial markets. '
        'private: everything related to private persons. '
        'others: everything else. '
        'Provide the classification, the confidence level (a float between 0.0 and 1.0), '
        'and a brief `reasoning` for your classification.' # UPDATED
    ),
)
logger.info("FirstClassificationAgent initialized.")


@first_classification_agent.tool
async def provide_context_for_first_classification(ctx: RunContext[str]) -> str:
    logger.debug(f"Tool 'provide_context_for_first_classification' called with deps: {ctx.deps}")
    return f"Context: {ctx.deps}"


logger.info("Initializing BitcoinClassificationAgent...")
bitcoin_classification_agent = Agent[None, Union[BitcoinClassification, Failed]](
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    output_type=Union[BitcoinClassification, Failed],  # type: ignore
    system_prompt=(
        'Based on this tweet from the President of the USA, decide if it could have an impact on the Bitcoin price. '
        'Provide a boolean for `bitcoin_impact` (True or False), a `confidence` level for your assessment '
        '(a float between 0.0 and 1.0), and a brief `reasoning` for your assessment.' # UPDATED
    ),
)
logger.info("BitcoinClassificationAgent initialized.")

# Agent 3: Bitcoin Price Direction Prediction
logger.info("Initializing BitcoinPriceDirectionAgent...")
bitcoin_price_direction_agent = Agent[None, Union[BitcoinPriceDirection, Failed]](
    os.getenv("MODEL", "groq:llama-3.3-70b-versatile"),
    output_type=Union[BitcoinPriceDirection, Failed],  # type: ignore
    system_prompt=(
        'Given this tweet from the President of the USA, which has been assessed to potentially impact the Bitcoin price: '
        '1. Predict whether the Bitcoin price is more likely to go "up", "down", or remain "neutral" as a result of this tweet. '
        '   Set this prediction to the `direction` field. '
        '2. Provide a `confidence` level for your prediction (a float between 0.0 and 1.0). '
        '3. Provide a brief `reasoning` for your prediction.' # Already existed
    ),
)
logger.info("BitcoinPriceDirectionAgent initialized.")


class ContentAnalyzer:
    def __init__(self):
        logger.info("Initializing ContentAnalyzer...")
        # Agent initialization is now at the module level, so they are ready when ContentAnalyzer is instantiated.

    def analyze_content(self, content: str, status_id_for_logging: str = "N/A"):
        """
        Analyzes the given content using a pipeline of AI agents.
        Logs the status_id with each major step for better traceability.
        """
        logger.info(f"Status ID [{status_id_for_logging}]: Starting agent pipeline for content analysis.")
        try:
            # --- Step 1: First Classification ---
            logger.info(f"Status ID [{status_id_for_logging}]: Running first classification (market/private/others)...")
            result_first_classification = first_classification_agent.run_sync(content, deps="General Knowledge")

            if isinstance(result_first_classification.output, Failed):
                logger.warning(
                    f"Status ID [{status_id_for_logging}]: First classification agent failed or was unable to determine a class. Result: {result_first_classification.output}")
            elif isinstance(result_first_classification.output, FirstClassification):
                logger.info(
                    f"Status ID [{status_id_for_logging}]: First classification result: "
                    f"Classification='{result_first_classification.output.classification}', "
                    f"Confidence={result_first_classification.output.confidence:.2f}, "
                    f"Reasoning='{result_first_classification.output.reasoning}'" # UPDATED LOGGING
                )

                # --- Step 2: Bitcoin Impact (only if first classification is 'market') ---
                if result_first_classification.output.classification == "market":
                    logger.info(f"Status ID [{status_id_for_logging}]: First classification is 'market'. Proceeding to Bitcoin impact classification.")

                    logger.info(f"Status ID [{status_id_for_logging}]: Running Bitcoin impact classification...")
                    result_bitcoin_classification = bitcoin_classification_agent.run_sync(content)

                    if isinstance(result_bitcoin_classification.output, Failed):
                        logger.warning(
                            f"Status ID [{status_id_for_logging}]: Bitcoin impact classification agent failed or was unable to determine impact. Result: {result_bitcoin_classification.output}")
                    elif isinstance(result_bitcoin_classification.output, BitcoinClassification):
                        logger.info(
                            f"Status ID [{status_id_for_logging}]: Bitcoin impact classification result: "
                            f"Bitcoin Impact='{result_bitcoin_classification.output.bitcoin_impact}', "
                            f"Confidence={result_bitcoin_classification.output.confidence:.2f}, "
                            f"Reasoning='{result_bitcoin_classification.output.reasoning}'" # UPDATED LOGGING
                        )

                        # --- Step 3: Bitcoin Price Direction (only if impact is True) ---
                        if result_bitcoin_classification.output.bitcoin_impact is True:
                            logger.info(
                                f"Status ID [{status_id_for_logging}]: Tweet assessed to have Bitcoin impact. Proceeding to Bitcoin price direction prediction.")

                            logger.info(f"Status ID [{status_id_for_logging}]: Running Bitcoin price direction prediction...")
                            result_price_direction = bitcoin_price_direction_agent.run_sync(content)

                            if isinstance(result_price_direction.output, Failed):
                                logger.warning(
                                    f"Status ID [{status_id_for_logging}]: Bitcoin price direction prediction agent failed. Result: {result_price_direction.output}")
                            elif isinstance(result_price_direction.output, BitcoinPriceDirection):
                                logger.info(
                                    f"Status ID [{status_id_for_logging}]: Bitcoin price direction prediction: "
                                    f"Direction='{result_price_direction.output.direction}', "
                                    f"Confidence={result_price_direction.output.confidence:.2f}, "
                                    f"Reasoning='{result_price_direction.output.reasoning}'" # Already logged reasoning
                                )
                            else:
                                logger.error(
                                    f"Status ID [{status_id_for_logging}]: Bitcoin price direction agent returned an unexpected Pydantic model type: {type(result_price_direction.output)}")
                        else:
                            logger.info(
                                f"Status ID [{status_id_for_logging}]: Tweet assessed to NOT have Bitcoin impact (Impact: {result_bitcoin_classification.output.bitcoin_impact}). Skipping price direction prediction.")
                    else:
                        logger.error(
                            f"Status ID [{status_id_for_logging}]: Bitcoin impact classification agent returned an unexpected Pydantic model type: {type(result_bitcoin_classification.output)}")
                else:
                    logger.info(
                        f"Status ID [{status_id_for_logging}]: First classification is '{result_first_classification.output.classification}', not 'market'. Skipping Bitcoin-related classifications.")
            else:
                logger.error(
                    f"Status ID [{status_id_for_logging}]: First classification agent returned an unexpected Pydantic model type: {type(result_first_classification.output)}")

        except Exception as e:
            logger.error(f"Status ID [{status_id_for_logging}]: An unexpected error occurred during agent processing: {e}", exc_info=True)

