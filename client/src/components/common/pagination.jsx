import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Cursor-based pagination controls. The backend drives paging through opaque
 * cursors, so this only reports intent — the parent owns cursor history.
 */
export function CursorPagination({ hasPrev, hasNext, onPrev, onNext, className }) {
  return (
    <nav aria-label="Pagination" className={cn("flex items-center justify-end gap-2", className)}>
      <Button
        variant="outline"
        size="sm"
        disabled={!hasPrev}
        onClick={onPrev}
        aria-label="Previous page"
      >
        <ChevronLeft aria-hidden="true" />
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!hasNext}
        onClick={onNext}
        aria-label="Next page"
      >
        Next
        <ChevronRight aria-hidden="true" />
      </Button>
    </nav>
  );
}
