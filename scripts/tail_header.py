import csv
import sys

reader = csv.DictReader(sys.stdin)

headers = {field: field if field.endswith('_key') else field.split('.')[-1]
           for field in reader.fieldnames}

writer = csv.DictWriter(sys.stdout, fieldnames=reader.fieldnames)

writer.writerow(headers)
writer.writerows(reader)
