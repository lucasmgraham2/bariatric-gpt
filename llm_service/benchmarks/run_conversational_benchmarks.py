import json
import os
import requests
from datetime import datetime, timedelta
from evaluator import evaluate_response

# Configuration
API_BASE = "http://localhost:8001"
ENDPOINT = "/api/v1/invoke_agent_graph"
CONV_BENCHMARK_FILE = os.path.join(os.path.dirname(__file__), "conversational_benchmark_dataset.json")

def load_dataset(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def run_conversational_benchmarks():
    print(f"Loading conversational benchmarks from {CONV_BENCHMARK_FILE}...\n")
    dataset = load_dataset(CONV_BENCHMARK_FILE)
    test_cases = dataset.get("test_cases", [])
    
    today = datetime.now()
    
    import time
    passed = 0
    failed = 0
    results_log = []
    latencies = []
    
    # Trackers for detailed statistics
    stats_by_category = {}
    stats_by_diet = {}
    stats_by_activity = {}
    
    for case in test_cases:
        test_id = case.get("id")
        category = case.get("category")
        offset_days = case.get("target_surgery_offset_days")
        profile = case.get("profile", {}).copy()
        
        # Dynamically calculate surgery date
        calculated_date = today - timedelta(days=offset_days)
        if profile.get("surgery_date") == "DYNAMIC_CALCULATED_DATE":
            profile["surgery_date"] = calculated_date.strftime("%Y-%m-%d")
            
        print(f"\n{'='*70}")
        print(f"=== Running Conversational Test: {test_id} ({category}) ===")
        print(f"Calculated Surgery Date: {profile['surgery_date']} (Offset: {offset_days} days)")
        print(f"{'='*70}")
        
        results_log.append(f"## Conversational Test {test_id} ({category})\n")
        results_log.append(f"**Calculated Surgery Date**: {profile['surgery_date']}\n\n")
        
        # Extract profile details for stats
        diet_type = profile.get("diet_type", "Unknown")
        activity_level = profile.get("activity_level", "Unknown")
        
        # Initialize stats for this test if not exists
        for d, key in [(stats_by_category, category), (stats_by_diet, diet_type), (stats_by_activity, activity_level)]:
            if key not in d:
                d[key] = {"pass": 0, "fail": 0}
        
        # State tracker for the conversation
        current_conversation_log = "[]"
        
        turns = case.get("turns", [])
        for i, turn in enumerate(turns):
            user_msg = turn.get("user_message")
            expected = turn.get("expected_guidance")
            
            print(f"\n--- Turn {i+1} ---")
            print(f"User: {user_msg}")
            
            payload = {
                "message": user_msg,
                "user_id": f"test_user_{test_id}",
                "patient_id": f"pat_{test_id}",
                "profile": profile,
                "memory": "",  # Starting fresh, though could be seeded
                "conversation_log": current_conversation_log,
                "debug": False
            }
            
            try:
                start_time = time.time()
                response = requests.post(f"{API_BASE}{ENDPOINT}", json=payload, timeout=120)
                exec_time = time.time() - start_time
                latencies.append(exec_time)
                
                if response.status_code == 200:
                    result = response.json()
                    ai_text = result.get("response_text", "No response")
                    
                    print(f"\nAI: {ai_text}")
                    print(f"\n[Expected Guidance: {expected}]")
                    
                    print("\nRunning Gemini Evaluation...")
                    eval_result = evaluate_response(
                        user_query=user_msg, 
                        actual_response=ai_text, 
                        expected_guidance=expected, 
                        context=profile,
                        simulated_today_str=today.strftime("%Y-%m-%d")
                    )
                    
                    if eval_result.get("passed"):
                        print(f"EVALUATION: PASS - {eval_result.get('rationale')}")
                        results_log.append(f"### Turn {i+1} - PASS\n")
                        passed += 1
                        stats_by_category[category]["pass"] += 1
                        stats_by_diet[diet_type]["pass"] += 1
                        stats_by_activity[activity_level]["pass"] += 1
                    else:
                        print(f"EVALUATION: FAIL - {eval_result.get('rationale')}")
                        results_log.append(f"### Turn {i+1} - FAIL\n")
                        failed += 1
                        stats_by_category[category]["fail"] += 1
                        stats_by_diet[diet_type]["fail"] += 1
                        stats_by_activity[activity_level]["fail"] += 1
                        
                    results_log.append(f"**Execution Time**: {exec_time:.2f} seconds\n\n")
                    results_log.append(f"**Parameters sent to LLM**:\n```json\n{json.dumps(payload, indent=2)}\n```\n\n")
                    results_log.append(f"**Parameters sent to Evaluator**:\n"
                                       f"- **user_query**: {user_msg}\n"
                                       f"- **actual_response**: {ai_text}\n"
                                       f"- **expected_guidance**: {expected}\n"
                                       f"- **context**: {json.dumps(profile)}\n"
                                       f"- **simulated_today_str**: {today.strftime('%Y-%m-%d')}\n\n")
                    results_log.append(f"**Gemini Evaluation Rationale**: {eval_result.get('rationale')}\n\n---\n")
                    
                    # Update the conversation log for the next turn!
                    # The LLM service returns the updated log in the response payload
                    if "conversation_log" in result:
                        current_conversation_log = result["conversation_log"]
                        
                else:
                    print(f"Failed with status code: {response.status_code}")
                    results_log.append(f"### Turn {i+1} - ERROR (Status: {response.status_code})\n\n---\n")
                    failed += 1
                    stats_by_category[category]["fail"] += 1
                    stats_by_diet[diet_type]["fail"] += 1
                    stats_by_activity[activity_level]["fail"] += 1
                    break # Stop this test case on failure
                    
            except Exception as e:
                print(f"Error testing turn {i+1}: {e}")
                results_log.append(f"### Turn {i+1} - ERROR ({e})\n\n---\n")
                failed += 1
                stats_by_category[category]["fail"] += 1
                stats_by_diet[diet_type]["fail"] += 1
                stats_by_activity[activity_level]["fail"] += 1
                break

    total = passed + failed
    print("\n" + "="*50)
    print("CONVERSATIONAL BENCHMARK SUMMARY")
    print("="*50)
    print(f"Total Turns Evaluated: {total}")
    print(f"Successful Calls: {passed}")
    print(f"Failed Calls: {failed}")
    if passed > 0:
        avg_time = sum(latencies) / len(latencies)
        print(f"Average Response Time: {avg_time:.2f} seconds")
        print(f"Max Response Time: {max(latencies):.2f} seconds")

    def print_stats(title, stat_dict):
        print(f"\n--- {title} ---")
        for k, v in stat_dict.items():
            tot = v['pass'] + v['fail']
            pct = (v['pass'] / tot * 100) if tot > 0 else 0
            print(f"{k}: {v['pass']}/{tot} ({pct:.1f}%)")

    print_stats("By Category", stats_by_category)
    print_stats("By Diet Type", stats_by_diet)
    print_stats("By Activity Level", stats_by_activity)
    print("="*50)
    
    # Write report
    report_file = os.path.join(os.path.dirname(__file__), "conversational_benchmark_results.md")
    with open(report_file, "w") as f:
        f.write("# Bariatric GPT Conversational Benchmark Results\n")
        f.write(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Overview\n")
        f.write(f"- **Total Turns Evaluated**: {total}\n")
        f.write(f"- **Successes**: {passed}\n")
        f.write(f"- **Failures**: {failed}\n")
        if passed > 0:
            f.write(f"- **Avg Latency**: {avg_time:.2f} seconds\n")
            
        def write_stats(title, stat_dict):
            f.write(f"\n### {title}\n")
            f.write("| Key | Pass | Fail | Total | Accuracy |\n")
            f.write("|-----|------|------|-------|----------|\n")
            for k, v in stat_dict.items():
                tot = v['pass'] + v['fail']
                pct = (v['pass'] / tot * 100) if tot > 0 else 0
                f.write(f"| {k} | {v['pass']} | {v['fail']} | {tot} | {pct:.1f}% |\n")
                
        write_stats("By Category (Phase)", stats_by_category)
        write_stats("By Diet Type", stats_by_diet)
        write_stats("By Activity Level", stats_by_activity)
        
        f.write("\n## Detailed Logs\n\n")
        f.writelines(results_log)
        
    print(f"Detailed report saved to {report_file}")

if __name__ == "__main__":
    run_conversational_benchmarks()
