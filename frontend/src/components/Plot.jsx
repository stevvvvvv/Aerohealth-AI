import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";
import { plotConfig } from "../theme.js";

const PlotlyComponent = createPlotlyComponent(Plotly);

export default function Plot({ height = 300, config, ...props }) {
  return (
    <PlotlyComponent
      useResizeHandler
      style={{ width: "100%", height }}
      config={{ ...plotConfig, ...config }}
      {...props}
    />
  );
}
