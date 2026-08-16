import sys, json
sys.path.insert(0, r'c:\Users\vyass\OneDrive\Documents\intern task\genar')
sys.stdout.reconfigure(encoding='utf-8')

from data_loader import load_dataset
from analysis import run_all_analyses

data = load_dataset(r'c:\Users\vyass\OneDrive\Documents\intern task\Bisoprolol_icsr_sample_1068rows.xlsx')
results = run_all_analyses(data, top_n=20)

# Verify key numbers
tc = results["total_cases"]["data"]
print("Total cases:", tc["total"])

sb = results["serious_breakdown"]["data"]
print(f"Serious: {sb['serious']} ({sb['serious_pct']}%), Non-serious: {sb['non_serious']}")

sx = results["sex_breakdown"]["data"]
print("Sex:", [(g["sex"], g["count"]) for g in sx["groups"]])

ag = results["age_group_breakdown"]["data"]
print("Age groups:", [(g["age_group"], g["count"]) for g in ag["groups"]])

tr = results["top_reactions"]["data"]
print(f"Top 5 reactions (of {tr['total_reactions_counted']} counted, {tr['flagged_rows_excluded']} excluded):")
for r in tr["reactions"][:5]:
    print(f"  {r['reaction']}: {r['count']}")

mv = results["monthly_case_volume"]["data"]
print(f"Monthly volume ({mv['total_months']} months):")
for m in mv["months"][:3]:
    print(f"  {m['month']}: {m['count']}")

exp = results["expedited_breakdown"]["data"]
print(f"Expedited: {exp['expedited']} ({exp['expedited_pct']}%)")

sc = results["seriousness_criteria"]["data"]
print("Seriousness criteria:")
for col, info in sc["criteria"].items():
    print(f"  {info['label']}: {info['count']} ({info['pct']}%)")

cl = results["case_listing"]["data"]
print(f"Case listing: {cl['total']} cases")
