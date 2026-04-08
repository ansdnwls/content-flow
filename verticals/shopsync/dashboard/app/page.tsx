import config from "../../config.json";
import { DistributionMap, AnalyticsOverview } from "@contentflow/ui/widgets";
import { engine } from "../lib/api";

interface ProductItem {
  readonly id: string;
  readonly name?: string;
  readonly text?: string;
  readonly status: string;
  readonly platforms?: readonly string[];
  readonly created_at: string;
}

async function getProducts(): Promise<{
  data: readonly ProductItem[];
  total: number;
}> {
  const res = await engine.listProducts(1, 10);
  if (res.data && "data" in (res.data as object)) {
    return res.data as { data: readonly ProductItem[]; total: number };
  }
  return { data: Array.isArray(res.data) ? (res.data as ProductItem[]) : [], total: 0 };
}

function ProductList({
  products,
}: {
  products: { data: readonly ProductItem[]; total: number };
}) {
  if (products.total === 0) {
    return (
      <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
        <h3 className="font-semibold mb-4 text-[var(--color-text)]">Products</h3>
        <p className="text-[var(--color-text)]/50 text-sm">
          No products yet. Create your first product listing to start selling everywhere.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">
        Products ({products.total})
      </h3>
      <ul className="space-y-3">
        {products.data.slice(0, 5).map((p) => (
          <li
            key={p.id}
            className="flex items-center justify-between rounded-lg bg-[var(--color-bg)] p-3"
          >
            <div>
              <p className="font-medium text-[var(--color-text)]">
                {p.name ?? p.text?.slice(0, 40) ?? "Untitled"}
              </p>
              <p className="text-xs text-[var(--color-text)]/50">
                {new Date(p.created_at).toLocaleDateString()}
              </p>
            </div>
            <span
              className={`text-xs px-2 py-1 rounded ${
                p.status === "published"
                  ? "bg-green-500/20 text-green-400"
                  : "bg-[var(--color-accent)]/20 text-[var(--color-accent)]"
              }`}
            >
              {p.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PriceAlerts() {
  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">Price Alerts</h3>
      <p className="text-[var(--color-text)]/50 text-sm">No active alerts</p>
    </div>
  );
}

export default async function DashboardHome() {
  let products: { data: readonly ProductItem[]; total: number } = {
    data: [],
    total: 0,
  };

  try {
    products = await getProducts();
  } catch {
    // API unavailable — render with empty data
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6 text-[var(--color-text)]">
        Welcome to {config.name}
      </h1>
      <div className="grid md:grid-cols-2 gap-6">
        <ProductList products={products} />
        <PriceAlerts />
        <DistributionMap key="distribution_map" />
        <AnalyticsOverview key="analytics_overview" />
      </div>
    </div>
  );
}
