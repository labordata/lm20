from olms.contracts import FormContract


class FilersFormContract(FormContract):
    name = "filers_form"
    formdata = {"clearCache": "F", "page": "1"}


class FilingsFormContract(FormContract):
    name = "filings_form"
    formdata = {"srNum": "C-297"}


class EmployersFormContract(FormContract):
    name = "employers_form"
    formdata = {"rptId": "731598"}
