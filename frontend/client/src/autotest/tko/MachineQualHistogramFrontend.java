package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.Utils;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;
import autotest.tko.TableView.TableViewConfig;

import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.Map;

public class MachineQualHistogramFrontend extends GraphingFrontend {
    
    @Override
    protected void addToHistory(Map<String, String> args) {
        globalFilters.addToHistory(args, "globalFilter");
        testFilters.addToHistory(args, "testFilter");
        args.put("interval", interval.getText());
    }
    
    @Override
    protected void handleHistoryArguments(Map<String, String> args) {
        setVisible(false);
        globalFilters.reset();
        testFilters.reset();
        globalFilters.handleHistoryArguments(args, "globalFilter");
        testFilters.handleHistoryArguments(args, "testFilter");
        interval.setText(args.get("interval"));
        setVisible(true);
    }
    
    private PreconfigSelector preconfig = new PreconfigSelector("qual", this);
    private FilterSelector globalFilters =
        new FilterSelector(DBColumnSelector.TEST_VIEW);
    private FilterSelector testFilters =
        new FilterSelector(DBColumnSelector.TEST_VIEW);
    private TextBox interval = new TextBox();
    private Button graphButton = new Button("Graph");
    private HTML graph = new HTML();
    
    public MachineQualHistogramFrontend(final TabView parent) {
        interval.setText("10");
        
        graphButton.addClickListener(new ClickListener() {
            public void onClick(Widget w) {
                parent.updateHistory();
                graph.setVisible(false);
                embeddingLink.setVisible(false);
                
                JSONObject params = buildParams();
                if (params == null) {
                    return;
                }
                
                rpcProxy.rpcCall("create_qual_histogram", params, new JsonRpcCallback() {
                    @Override
                    public void onSuccess(JSONValue result) {
                        graph.setHTML(Utils.jsonToString(result));
                        graph.setVisible(true);
                        embeddingLink.setVisible(true);
                    }
                });
            }
        });
        
        addControl("Preconfigured:", preconfig);
        addControl("Global filters:", globalFilters);
        addControl("Test set filters:", testFilters);
        addControl("Interval:", interval);
        
        table.setWidget(table.getRowCount(), 1, graphButton);
        table.setWidget(table.getRowCount(), 0, graph);
        table.getFlexCellFormatter().setColSpan(table.getRowCount() - 1, 0, 3);
        
        table.setWidget(table.getRowCount(), 2, embeddingLink);
        table.getFlexCellFormatter().setHorizontalAlignment(
                table.getRowCount() - 1, 2, HasHorizontalAlignment.ALIGN_RIGHT);
        
        graph.setVisible(false);
        embeddingLink.setVisible(false);
        
        initWidget(table);
    }
    
    @Override
    public void refresh() {
        // nothing to refresh
    }
    
    @Override
    protected native void setDrilldownTrigger() /*-{
        var instance = this;
        $wnd.showQualDrilldown = function(filterString) {
            instance.@autotest.tko.MachineQualHistogramFrontend::showDrilldown(Ljava/lang/String;)(filterString);
        }
        $wnd.showQualNADialog = function(hosts) {
            instance.@autotest.tko.MachineQualHistogramFrontend::showNADialog(Ljava/lang/String;)(hosts);
        }
        $wnd.showQualEmptyDialog = function() {
            instance.@autotest.tko.MachineQualHistogramFrontend::showEmptyDialog()();
        }
    }-*/;
    
    @Override
    protected void addAdditionalEmbeddingParams(JSONObject params) {
        params.put("graph_type", new JSONString("qual"));
        params.put("params", buildParams());
    }
    
    @SuppressWarnings("unused")
    private void showDrilldown(final String filterString) {
        CommonPanel.getPanel().setCondition(new TestSet() {
            public String getCondition() {
                return filterString;
            }
            
            public boolean isSingleTest() {
                return false;
            }
        });
        listener.onSwitchToTable(TableViewConfig.PASS_RATE);
    }
    
    @SuppressWarnings("unused")
    private void showNADialog(String hosts) {
        new GraphingDialog("Did not run any of the selected tests:", new HTML(hosts)).center();
    }
    
    @SuppressWarnings("unused")
    private void showEmptyDialog() {
        new GraphingDialog("No hosts in this pass rate range", new HTML()).center();
    }
    
    private JSONString buildQuery() {
        String gFilterString = globalFilters.getFilterString();
        String tFilterString = testFilters.getFilterString();
        boolean hasGFilter = !gFilterString.equals("");
        boolean hasTFilter = !tFilterString.equals("");
        
        StringBuilder sql = new StringBuilder();
        
        sql.append("SELECT hostname, COUNT(DISTINCT ");
        if (hasTFilter) {
            sql.append("IF(");
            sql.append(tFilterString);
            sql.append(", test_idx, NULL)");
        } else {
            sql.append("test_idx");
        }
        sql.append(") 'total', COUNT(DISTINCT IF(");
        if (hasTFilter) {
            sql.append("(");
            sql.append(tFilterString);
            sql.append(") AND ");
        }
        
        sql.append("status = 'GOOD', test_idx, NULL)) 'good' FROM test_view_outer_joins");
        if (hasGFilter) {
            sql.append(" WHERE ");
            sql.append(gFilterString);
        }
        sql.append(" GROUP BY hostname");
        return new JSONString(sql.toString());
    }
    
    private JSONString buildFilterString() {
        StringBuilder filterString = new StringBuilder();
        String gFilterString = globalFilters.getFilterString();
        String tFilterString = testFilters.getFilterString();
        boolean hasGFilter = !gFilterString.equals("");
        boolean hasTFilter = !tFilterString.equals("");
        if (hasGFilter) {
            filterString.append("(");
            filterString.append(gFilterString);
            filterString.append(")");
            if (hasTFilter) {
                filterString.append(" AND ");
            }
        }
        if (hasTFilter) {
            filterString.append("(");
            filterString.append(tFilterString);
            filterString.append(")");
        }
        return new JSONString(filterString.toString());
    }
    
    private JSONObject buildParams() {
        if (interval.getText().equals("")) {
            NotifyManager.getInstance().showError("You must enter an interval");
            return null;
        }
        
        int intervalValue;
        try {
            intervalValue = Integer.parseInt(interval.getText());
        } catch (NumberFormatException e) {
            NotifyManager.getInstance().showError("Interval must be an integer");
            return null;
        }
        
        JSONObject params = new JSONObject();
        params.put("query", buildQuery());
        params.put("filter_string", buildFilterString());
        params.put("interval", new JSONNumber(intervalValue));
        
        return params;
    }
}
