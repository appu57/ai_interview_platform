import argparse
import csv
import statistics
import sys


def load_scored_csv(path):
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize(path):
    rows = load_scored_csv(path)
    n = len(rows)
    if n == 0:
        print(f"{path}: no rows found.")
        return

    stopped_rate = sum(1 for r in rows if r["stopped"].lower() == "true") / n
    length_ok_rate = sum(1 for r in rows if r["length_bucket_ok"].lower() == "true") / n
    double_answer_rate = sum(1 for r in rows if r["possible_double_answer"].lower() == "true") / n

    accuracy_scores = [safe_float(r["accuracy_score_1to5"]) for r in rows]
    accuracy_scores = [s for s in accuracy_scores if s is not None]
    completeness_scores = [safe_float(r["completeness_score_1to5"]) for r in rows]
    completeness_scores = [s for s in completeness_scores if s is not None]
    spoken_scores = [safe_float(r["spoken_style_score_1to5"]) for r in rows]
    spoken_scores = [s for s in spoken_scores if s is not None]

    concept_scores = [safe_float(r.get("concept_coverage_recall")) for r in rows]
    concept_scores = [s for s in concept_scores if s is not None]
    judge_accuracy = [safe_float(r.get("llm_judge_accuracy")) for r in rows]
    judge_accuracy = [s for s in judge_accuracy if s is not None]
    judge_completeness = [safe_float(r.get("llm_judge_completeness")) for r in rows]
    judge_completeness = [s for s in judge_completeness if s is not None]

    unscored = n - len(accuracy_scores)

    print(f"\n{'='*70}\n{path}\n{'='*70}")
    print(f"Entries: {n}")
    print(f"Stopped naturally:        {stopped_rate*100:.0f}%")
    print(f"Length within expected:   {length_ok_rate*100:.0f}%")
    print(f"Possible double-answer:   {double_answer_rate*100:.0f}%  (lower is better)")
    if concept_scores:
        print(f"Avg concept coverage:     {statistics.mean(concept_scores)*100:.0f}%  (n={len(concept_scores)}, "
              f"entries with no required_concepts excluded)")
    if judge_accuracy:
        print(f"Avg LLM-judge accuracy:     {statistics.mean(judge_accuracy):.2f} / 5  (n={len(judge_accuracy)})")
    if judge_completeness:
        print(f"Avg LLM-judge completeness: {statistics.mean(judge_completeness):.2f} / 5  (n={len(judge_completeness)})")
    if accuracy_scores:
        print(f"Avg HUMAN accuracy score:       {statistics.mean(accuracy_scores):.2f} / 5  (n={len(accuracy_scores)})")
    if completeness_scores:
        print(f"Avg HUMAN completeness score:   {statistics.mean(completeness_scores):.2f} / 5  (n={len(completeness_scores)})")
    if spoken_scores:
        print(f"Avg HUMAN spoken-style score:   {statistics.mean(spoken_scores):.2f} / 5  (n={len(spoken_scores)})")
    if unscored:
        print(f"\nNOTE: {unscored}/{n} entries have no human scores yet -- "
              f"fill in the CSV before treating these numbers as final.")

    # Flag anything with a known_risk tag so it's not lost in the aggregate
    risky = [r for r in rows if r.get("known_risk")]
    if risky:
        print(f"\nEntries with a known_risk tag (check these individually, "
              f"aggregates can hide a single bad case):")
        for r in risky:
            print(f"  [{r['id']}] {r['known_risk']} -- {r.get('human_notes') or '(no human_notes yet)'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_paths", nargs="+", help="One or more golden_eval_*.csv files to compare")
    args = parser.parse_args()

    for path in args.csv_paths:
        summarize(path)

    print(f"\n{'='*70}")
    print("Read the actual response_text for anything with a low score or a")
    print("known_risk tag before deciding a model version is better -- these")
    print("numbers summarize your own judgment, they don't replace it.")


if __name__ == "__main__":
    main()