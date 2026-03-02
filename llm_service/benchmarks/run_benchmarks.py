import json
import os
import requests
from datetime import datetime, timedelta
from evaluator import evaluate_response

# Configuration
API_BASE = "http://localhost:8001"  # Directly querying LLM service
ENDPOINT = "/api/v1/invoke_agent_graph"
BENCHMARK_FILE = os.path.join(os.path.dirname(__file__), "bariatric_benchmark_dataset.json")

def load_dataset(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def run_benchmarks():
    print(f"Loading benchmarks from {BENCHMARK_FILE}...\n")
    dataset = load_dataset(BENCHMARK_FILE)
    test_cases = dataset.get("test_cases", [])
    
    today = datetime.now()
    
    passed = 0
    failed = 0
    results_log = []
    latencies = []
    
    # Trackers for detailed statistics
    stats_by_category = {}
    stats_by_diet = {}
    stats_by_activity = {}
    
    import time
    
    for case in test_cases:
        test_id = case.get("id")
        category = case.get("category")
        offset_days = case.get("target_surgery_offset_days")
        
        # 1. Dynamically calculate the surgery date!
        # If target_surgery_offset_days = 20, they had surgery 20 days ago (Subtract 20 from today)
        # If target_surgery_offset_days = -14, they have surgery in 14 days (Subtract -14, meaning add 14)
        calculated_date = today - timedelta(days=offset_days)
        date_str = calculated_date.strftime("%Y-%m-%d")
        
        # 2. Inject this dynamically calculated date into the payload
        payload = case.get("simulated_payload").copy()
        
        if "profile" in payload and "surgery_date" in payload["profile"]:
            if payload["profile"]["surgery_date"] == "DYNAMIC_CALCULATED_DATE":
                payload["profile"]["surgery_date"] = date_str
                
        print(f"=== Running Test: {test_id} ({category}) ===")
        print(f"Calculated Surgery Date: {date_str} (Offset: {offset_days} days)")
        print(f"Query: {payload['message']}")
        
        # Extract profile details for stats
        profile = case.get("simulated_payload", {}).get("profile", {})
        diet_type = profile.get("diet_type", "Unknown")
        activity_level = profile.get("activity_level", "Unknown")
        
        # Initialize stats for this test if not exists
        for d, key in [(stats_by_category, category), (stats_by_diet, diet_type), (stats_by_activity, activity_level)]:
            if key not in d:
                d[key] = {"pass": 0, "fail": 0}
                
        # 3. Send to LLM
        try:
            print("Waiting for LLM response...")
            start_time = time.time()
            response = requests.post(
                f"{API_BASE}{ENDPOINT}", 
                json=payload,
                timeout=120
            )
            exec_time = time.time() - start_time
            latencies.append(exec_time)
            
            if response.status_code == 200:
                result = response.json()
                ai_text = result.get("response_text", "No response text found")
                
                print("\nReceived AI Response:")
                print("-" * 40)
                print(ai_text)
                print("-" * 40)
                print(f"Expected Guidance: {case.get('expected_guidance')}")
                print("*" * 60)
                
                print("\nRunning Gemini Evaluation...")
                eval_result = evaluate_response(
                    user_query=payload['message'], 
                    actual_response=ai_text, 
                    expected_guidance=case.get('expected_guidance'), 
                    context=profile,
                    simulated_today_str=today.strftime("%Y-%m-%d")
                )
                
                if eval_result.get("passed"):
                    print(f"EVALUATION: PASS - {eval_result.get('rationale')}")
                    results_log.append(f"### Test {test_id} ({category}) - PASS\n")
                    passed += 1
                    stats_by_category[category]["pass"] += 1
                    stats_by_diet[diet_type]["pass"] += 1
                    stats_by_activity[activity_level]["pass"] += 1
                else:
                    print(f"EVALUATION: FAIL - {eval_result.get('rationale')}")
                    results_log.append(f"### Test {test_id} ({category}) - FAIL\n")
                    failed += 1
                    stats_by_category[category]["fail"] += 1
                    stats_by_diet[diet_type]["fail"] += 1
                    stats_by_activity[activity_level]["fail"] += 1
                
                # Format for recording
                results_log.append(f"**Calculated Surgery Date**: {date_str}\n")
                results_log.append(f"**Execution Time**: {exec_time:.2f} seconds\n\n")
                results_log.append(f"**Parameters sent to LLM**:\n```json\n{json.dumps(payload, indent=2)}\n```\n\n")
                results_log.append(f"**Parameters sent to Evaluator**:\n"
                                   f"- **user_query**: {payload['message']}\n"
                                   f"- **actual_response**: {ai_text}\n"
                                   f"- **expected_guidance**: {case.get('expected_guidance')}\n"
                                   f"- **context**: {json.dumps(profile)}\n"
                                   f"- **simulated_today_str**: {today.strftime('%Y-%m-%d')}\n\n")
                results_log.append(f"**Gemini Evaluation Rationale**: {eval_result.get('rationale')}\n\n---\n")

            else:
                print(f"Failed with status code: {response.status_code}")
                results_log.append(f"### Test {test_id} ({category}) - ERROR\n")
                results_log.append(f"Status Code: {response.status_code}\n\n---\n")
                failed += 1
                stats_by_category[category]["fail"] += 1
                stats_by_diet[diet_type]["fail"] += 1
                stats_by_activity[activity_level]["fail"] += 1
                
        except Exception as e:
            print(f"Error testing case {test_id}: {e}")
            results_log.append(f"### Test {test_id} ({category}) - ERROR\n")
            results_log.append(f"Exception: {e}\n\n---\n")
            failed += 1
            stats_by_category[category]["fail"] += 1
            stats_by_diet[diet_type]["fail"] += 1
            stats_by_activity[activity_level]["fail"] += 1
            
    total = passed + failed
    print("\n" + "="*50)
    print("BENCHMARK SUMMARY")
    print("="*50)
    print(f"Total Tests: {total}")
    print(f"Successful API Calls: {passed}")
    print(f"Failed API Calls: {failed}")
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
    report_file = os.path.join(os.path.dirname(__file__), "benchmark_results.md")
    with open(report_file, "w") as f:
        f.write("# Bariatric GPT Benchmark Results\n")
        f.write(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Overview\n")
        f.write(f"- **Total Tests**: {total}\n")
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
    run_benchmarks()
