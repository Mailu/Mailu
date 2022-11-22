# GTUBE should be blocked, see https://rspamd.com/doc/gtube_patterns.html
python3 tests/email_test.py "XJS*C4JDBQADN1.NSBN3*2IDNEN*GTUBE-STANDARD-ANTI-UBE-TEST-EMAIL*C.34X"
if [ $? -eq 25 ]; then
	exit 0
else
	exit 1
fi
