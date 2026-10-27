"""Offline end-to-end research demo. Uses local files and a recording mock executor."""
import json
import pathlib
from demo_app import scan_document
from policy import load_policy, decide
from tool_auth import MockExecutor, authorize_and_execute

ROOT = pathlib.Path(__file__).resolve().parent


def run():
    policy = load_policy()
    examples = json.loads((ROOT / "demo/examples.json").read_text(encoding="utf-8"))
    documents = []
    for item in examples:
        scan = scan_document({"text":item["text"],"html":item["kind"]=="html"})
        policy_result=scan["policy"]
        detected=scan["ensemble_score"]>=scan["ensemble_threshold"]
        documents.append({"input":item,"scanner":{"raw_score":scan["ensemble_score"],"threshold":scan["ensemble_threshold"],"detector_scores":scan["scores"],"label":"possible_injection" if detected else "no_match","expected_injection":item["expected_injection"],"case_correct":detected==item["expected_injection"]},"sanitization":scan["sanitization"],"agent_view":scan["agent_view"],"policy":policy_result,"final_outcome":scan["final_outcome"]})

    executor = MockExecutor()
    requests = json.loads((ROOT / "demo/tool_requests.json").read_text(encoding="utf-8"))
    auth_results = []
    for item in requests:
        result = authorize_and_execute(item, executor)
        auth_results.append({"input": item, "authorization": result,
                             "final_outcome": result["outcome"]})
    authorization_cases_passed = executor.calls == ["lookup_public_help"] and all(
        r["authorization"]["executor_called"] == (r["authorization"]["tool"] == "lookup_public_help")
        for r in auth_results)

    # Independent policy checks exercise each decision and boundary.
    policy_cases = []
    for score, expected in ((0.1, "allow"), (0.5, "hold_for_review"), (0.9, "quarantine")):
        result = decide(score, policy)
        policy_cases.append({"score": score, "expected": expected, "result": result,
                             "passed": result["decision"] == expected and result["score"] == score})

    output = {"notice": "Research demo only. Scores and decisions are screening signals, not proof of compromise.",
              "scanner": {"cases": documents, "passed": sum(d["scanner"]["case_correct"] for d in documents), "total": len(documents)},
              "document_policy": {"cases": policy_cases, "passed": sum(c["passed"] for c in policy_cases), "total": len(policy_cases)},
              "tool_authorization": {"cases": auth_results, "mock_executor_calls": executor.calls,
                                     "passed": authorization_cases_passed, "total": len(auth_results)},
              "quarantine_semantics": "decision is recorded only; no real file is moved or deleted"}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/demo_results.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    components={"scanner_detection":{"cases":documents,"passed":sum(d['scanner']['case_correct'] for d in documents),"total":len(documents)},"document_policy":{"cases":policy_cases,"passed":sum(c['passed'] for c in policy_cases),"total":len(policy_cases)},"tool_authorization":{"cases":auth_results,"passed":authorization_cases_passed,"total":len(auth_results),"mock_executor_calls":executor.calls},"notice":output['notice']}
    (ROOT / "reports/component_assessments.json").write_text(json.dumps(components,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
