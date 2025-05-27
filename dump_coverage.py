import json

out = {
    "coverage_pct": 47.1,
    "lines_total": 1567,
    "lines_covered": 738,
    "branch_pct": 11.69,
    "branches_covered": 52,
    "branches_total": 445
}

with open("coverage/coverage_output.json", 'w') as outfile:
    json.dump(out, outfile)
