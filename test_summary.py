from backend.models.model_loader import load_all_models
from backend.pipeline.summarization import summarize_document

print("Loading models...")
load_all_models()

text = """
Artificial Intelligence is transforming industries across healthcare,
finance, education, and manufacturing. Modern AI systems are capable
of analyzing large amounts of data.
"""

summary = summarize_document(text)

print(repr(summary))