package policy

deny contains msg if {
	input.tool == "<tool>"
	<a condition on input.args>
	msg := "<what is refused, and what to do instead>"
}
