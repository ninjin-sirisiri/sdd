# 0001. Land stacked PRs without restack

GitHub review on a lower stacked PR needs new commits, and the usual fix is to rebase descendants and force-push. Review fixes update the existing `sdd-stack/task-N` ref in place, descendants are not restacked, and the stack is integrated by landing from the bottom. Extra branches would break the merge chain, and restack would need force-push, which this pack does not allow.
