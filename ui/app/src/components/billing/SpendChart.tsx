import React from "react";
import {
  LineChart,
  DonutChart,
  IChartProps,
  ILineChartPoints,
  IChartDataPoint,
} from "@fluentui/react-charting";
import { Stack, Text } from "@fluentui/react";
import { WorkspaceBudget } from "../../models/billing";
import { formatCurrency } from "./billingFormat";

interface SpendChartProps {
  budget: WorkspaceBudget;
}

const palette = ["#0078d4", "#107c10", "#5c2e91", "#f7630c", "#038387", "#8764b8"];

export const SpendChart: React.FunctionComponent<SpendChartProps> = ({ budget }) => {
  // Cumulative spend over time vs allocation line.
  let running = 0;
  const cumulativePoints = budget.dailySpend.map((p) => {
    running += p.cost;
    return { x: new Date(p.date), y: Math.round(running * 100) / 100 };
  });

  // Budget allocation as a step function — reflects each top-up / amend on the
  // date it took effect (so history doesn't retroactively shift up).
  const history = [...budget.allocationHistory].sort((a, b) =>
    a.date.localeCompare(b.date),
  );
  const allocationOn = (dateStr: string): number => {
    let amount = history[0]?.amount ?? budget.allocated;
    for (const h of history) {
      if (h.date.slice(0, 10) <= dateStr) amount = h.amount;
      else break;
    }
    return amount;
  };

  const lineData: ILineChartPoints[] = [
    {
      legend: "Cumulative spend",
      data: cumulativePoints,
      color: "#0078d4",
    },
    {
      legend: "Budget",
      data: budget.dailySpend.map((p) => ({
        x: new Date(p.date),
        y: allocationOn(p.date),
      })),
      color: "#d13438",
      lineOptions: { strokeDasharray: "6 4" },
    },
  ];

  const lineChartData: IChartProps = {
    chartTitle: "Spend over time",
    lineChartData: lineData,
  };

  const donutData: IChartDataPoint[] = budget.serviceBreakdown.map((s, i) => ({
    legend: s.name,
    data: Math.round(s.cost * 100) / 100,
    color: palette[i % palette.length],
    xAxisCalloutData: s.name,
    yAxisCalloutData: formatCurrency(s.cost, budget.currency),
  }));

  const donutChartData: IChartProps = {
    chartTitle: "Cost by service",
    chartData: donutData,
  };

  return (
    <Stack horizontal tokens={{ childrenGap: 24 }} wrap>
      <Stack.Item grow={2} style={{ minWidth: 380 }}>
        <Text variant="mediumPlus" block styles={{ root: { fontWeight: 600, marginBottom: 8 } }}>
          Spend over time
        </Text>
        <div style={{ height: 260 }}>
          <LineChart
            key={`line-${budget.allocated}-${budget.consumed}`}
            data={lineChartData}
            height={260}
            width={520}
            yAxisTickCount={5}
            allowMultipleShapesForPoints
          />
        </div>
      </Stack.Item>
      <Stack.Item grow={1} style={{ minWidth: 260 }}>
        <Text variant="mediumPlus" block styles={{ root: { fontWeight: 600, marginBottom: 8 } }}>
          Cost by service
        </Text>
        <DonutChart
          key={`donut-${budget.consumed}`}
          data={donutChartData}
          innerRadius={55}
          height={260}
          width={260}
          valueInsideDonut={formatCurrency(budget.consumed, budget.currency)}
        />
      </Stack.Item>
    </Stack>
  );
};
