import { PageHeader } from "@/components/common/page-header";
import { ExceptionsView } from "@/components/domain/exceptions-view";

export const metadata = { title: "Exceptions" };

export default function ExceptionsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Exceptions"
        description="Issues the engine found in your data that need a human decision."
      />
      <ExceptionsView />
    </div>
  );
}
