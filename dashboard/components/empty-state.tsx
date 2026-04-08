import Image from "next/image";
import Link from "next/link";

type EmptyStateProps = {
  title: string;
  description: string;
  image: string;
  actionLabel?: string;
  actionHref?: string;
};

export function EmptyState({ title, description, image, actionLabel, actionHref }: EmptyStateProps) {
  return (
    <div className="empty-illustration">
      <div>
        <Image src={image} alt="" width={240} height={160} />
        <h2 className="text-2xl font-semibold text-text">{title}</h2>
        <p className="mt-2 max-w-md text-sm text-muted">{description}</p>
        {actionLabel && actionHref ? (
          <Link href={actionHref} className="btn-primary mt-5 inline-flex">
            {actionLabel}
          </Link>
        ) : null}
      </div>
    </div>
  );
}
