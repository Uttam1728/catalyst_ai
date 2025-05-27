set -e
mkdir -p artifacts
mkdir coverage
touch coverage/coverage_output.json
python3 dump_coverage.py
mv coverage/** /mnt/artifacts
