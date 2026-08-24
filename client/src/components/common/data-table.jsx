import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Financial table shell: consistent column alignment, hover states, loading
 * skeletons and empty/error slots. Domain screens pass column definitions;
 * this component owns none of the business semantics.
 *
 * columns: [{ key, header, align?: "right", className?, headerClassName?, render?(row) }]
 */
export function DataTable({
  columns,
  rows,
  rowKey,
  loading = false,
  skeletonRows = 8,
  empty,
  error,
  onRowClick,
  className,
}) {
  return (
    <div className={cn("overflow-hidden rounded-xl border border-border bg-card", className)}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left">
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={column.sortDirection}
                  className={cn(
                    "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground",
                    column.align === "right" && "text-right",
                    column.headerClassName
                  )}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {error ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  {error}
                </td>
              </tr>
            ) : loading ? (
              Array.from({ length: skeletonRows }).map((_, index) => (
                <tr key={index} className="border-b border-border/60 last:border-0">
                  {columns.map((column) => (
                    <td key={column.key} className="px-4 py-3.5">
                      <Skeleton
                        className={cn("h-4 w-full max-w-28", column.align === "right" && "ml-auto")}
                      />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  {empty}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onRowClick(row);
                          }
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-selected={undefined}
                  className={cn(
                    "border-b border-border/60 transition-colors last:border-0",
                    onRowClick &&
                      "cursor-pointer outline-none focus-visible:bg-muted/60 hover:bg-muted/40"
                  )}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        "px-4 py-3 align-middle tabular-nums",
                        column.align === "right" && "text-right",
                        column.className
                      )}
                    >
                      {column.render ? column.render(row) : row[column.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
