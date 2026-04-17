# Stage 1 Classifier Design Notes

Created: 2026-04-15

## Context

Jane's current v2 Stage 1 classifier is effectively a ChromaDB k-nearest-neighbor classifier:

```text
prompt -> embedding -> Chroma top-k nearest examples -> vote -> class/confidence
```

This is fast, but weak as the primary router because embedding similarity is not the same as intent equivalence. It struggles with near-boundary cases, negation, meta questions, side-effectful commands, and short context-dependent prompts like:

```text
yes
send it
cancel that
what about tomorrow
tell him that
```

Current Stage 1 is prompt-only. Conversation context enters later in Stage 2 or Stage 3, which means contextual prompts may miss the fast path.

## Desired Direction

Replace pure nearest-neighbor routing with a supervised classifier that supports calibrated abstention:

```text
prompt + compact structured context
  -> neural intent classifier
  -> top class + confidence + margin
  -> deterministic validator
  -> Stage 2 if safe, otherwise Stage 3
```

Chroma should become evidence/debug/active-learning support, not the main classifier.

## Candidate Model Families

Strong direct classifiers:

- `answerdotai/ModernBERT-base`
- `microsoft/deberta-v3-small`

Fast embedding / SetFit candidates:

- `BAAI/bge-base-en-v1.5`
- `BAAI/bge-small-en-v1.5`
- `sentence-transformers/all-MiniLM-L6-v2`
- `sentence-transformers/all-MiniLM-L12-v2`
- `sentence-transformers/all-mpnet-base-v2`
- `intfloat/e5-small-v2`
- `Alibaba-NLP/gte-base-en-v1.5`

Higher-quality but heavier embedding option:

- `Qwen/Qwen3-Embedding-0.6B`

Best initial experiments:

```text
1. ModernBERT-base fine-tuned classifier
2. DeBERTa-v3-small fine-tuned classifier
3. BGE-base or BGE-small with SetFit
```

## Confidence

Neural classifiers can emit class probabilities through:

```text
logits -> softmax -> class probabilities
```

But softmax confidence is not automatically trustworthy. Jane should use:

```text
calibrated confidence
+ top-vs-second margin
+ class-specific thresholds
+ validators
```

Recommended routing rule:

```text
if top_class != STAGE3
   and confidence >= threshold[top_class]
   and margin >= margin_threshold[top_class]
   and class_validator_passes:
       route to Stage 2
else:
       route to Stage 3
```

Example thresholds:

```text
SEND_MESSAGE:
  confidence >= 0.92
  margin >= 0.25
  validator required

WEATHER:
  confidence >= 0.75
  margin >= 0.15

GREETING:
  confidence >= 0.70
  margin >= 0.12

END_CONVERSATION:
  confidence >= 0.90
  margin >= 0.25
  active conversation state required
```

## Training Data Strategy

When adding a new class, generate a large supervised dataset:

```text
positive examples for the class
+ hard negative/adversarial examples
+ examples for sibling classes
+ explicit STAGE3 / DELEGATE_OPUS examples
```

The negative set is especially important. It should include boundary cases with the same vocabulary but different intent.

Example for `SEND_MESSAGE`:

Positive:

```text
text Mom I will be late
tell Kathia I love her
send Romeo a message saying thanks
```

Hard negatives:

```text
did Mom text me
why did the send-message handler fail
draft a message but do not send it
what should I text Kathia
do not text Mom yet
show me the code that sends SMS
```

Hard negatives should map to either the correct sibling class, such as `READ_MESSAGES`, or to `STAGE3` when the prompt needs general reasoning.

Synthetic generation target:

```text
2k-10k diverse positive examples per class
2k-10k hard negatives per class
```

Quality matters more than raw count. Avoid repetitive paraphrase templates that create fake confidence.

## Context Handling

The classifier should not see only the prompt. It should receive compact structured context:

```json
{
  "pending_action": "SEND_MESSAGE_CONFIRMATION",
  "last_intent": "SEND_MESSAGE",
  "entities": {
    "recipient": "Kathia",
    "draft_body": "I love you"
  },
  "recent_summary": "Jane drafted a text to Kathia and is waiting for confirmation.",
  "user_text": "yes"
}
```

This lets the model learn:

```text
context: pending SEND_MESSAGE_CONFIRMATION
user: yes
label: SEND_MESSAGE_CONFIRM
```

But without context:

```text
context: none
user: yes
label: STAGE3
```

## Structured FIFO Link

This classifier design depends on better context storage. Related job:

```text
/home/chieh/ambient/vessence/configs/job_queue/job_069_structured_fifo_context.md
```

That job proposes storing both structured context and prose summary in FIFO:

```text
structured fields for routing/state/tool logic
+ prose summary for Stage 3 continuity
```

## Proposed Production Shape

```text
1. Load active structured session state.
2. Resolve pending actions before generic classification.
3. Build compact classifier input from prompt + structured context.
4. Run fine-tuned neural classifier.
5. Read top class, confidence, and margin.
6. Apply class-specific validator.
7. Route to Stage 2 only when safe.
8. Otherwise escalate to Stage 3.
9. Log misses and hard cases for active learning.
```

## Main Principle

Stage 1 should become:

```text
supervised neural classifier with calibrated abstention
```

not:

```text
nearest-neighbor router
```

And Jane should never route side-effectful actions from classifier confidence alone. Side-effectful routes require confidence, margin, structured context where relevant, and deterministic validation.
