package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RightClickTable;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.TableActionsPanel;
import autotest.common.ui.TableActionsPanel.TableActionsListener;
import autotest.common.ui.TableSelectionPanel.SelectionPanelListener;
import autotest.tko.CommonPanel.CommonPanelListener;
import autotest.tko.Spreadsheet.CellInfo;
import autotest.tko.Spreadsheet.Header;
import autotest.tko.Spreadsheet.SpreadsheetListener;
import autotest.tko.TableView.TableSwitchListener;
import autotest.tko.TableView.TableViewConfig;
import autotest.tko.TkoUtils.FieldInfo;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.WindowResizeListener;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.MenuBar;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SpreadsheetView extends ConditionTabView 
                             implements SpreadsheetListener, TableActionsListener, 
                                        CommonPanelListener, SelectionPanelListener {
    private static final String HISTORY_ONLY_LATEST = "show_only_latest";
    public static final String DEFAULT_ROW = "kernel";
    public static final String DEFAULT_COLUMN = "platform";
    
    private static final String HISTORY_SHOW_INCOMPLETE = "show_incomplete";
    private static final String HISTORY_COLUMN = "column";
    private static final String HISTORY_ROW = "row";
    
    private static enum DrilldownType {DRILLDOWN_ROW, DRILLDOWN_COLUMN, DRILLDOWN_BOTH}
    
    private static JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private static JsonRpcProxy afeRpcProxy = JsonRpcProxy.getProxy(JsonRpcProxy.AFE_BASE_URL);
    private TableSwitchListener listener;
    protected List<HeaderField> currentRowFields;
    protected List<HeaderField> currentColumnFields;
    protected Map<String,String[]> drilldownMap = new HashMap<String,String[]>();
    private Map<String, HeaderField> headerFieldMap = new HashMap<String, HeaderField>();
    
    private HeaderSelect rowSelect = new HeaderSelect();
    private HeaderSelect columnSelect = new HeaderSelect();
    private CheckBox showIncomplete = new CheckBox("Show incomplete tests");
    private CheckBox showOnlyLatest = new CheckBox("Show only latest test per cell");
    private Button queryButton = new Button("Query");
    private TestGroupDataSource normalDataSource = TestGroupDataSource.getStatusCountDataSource();
    private TestGroupDataSource latestDataSource = TestGroupDataSource.getLatestTestsDataSource();
    private Spreadsheet spreadsheet = new Spreadsheet();
    private SpreadsheetDataProcessor spreadsheetProcessor = 
        new SpreadsheetDataProcessor(spreadsheet);
    private SpreadsheetSelectionManager selectionManager = 
        new SpreadsheetSelectionManager(spreadsheet, null);
    private TableActionsPanel actionsPanel = new TableActionsPanel(false);
    private RootPanel jobCompletionPanel;
    private boolean currentShowIncomplete;
    private boolean notYetQueried = true;
    
    public SpreadsheetView(TableSwitchListener listener) {
        this.listener = listener;
        commonPanel.addListener(this);
    }
    
    @Override
    public String getElementId() {
        return "spreadsheet_view";
    }

    @Override
    public void initialize() {
        normalDataSource.setSkipNumResults(true);
        latestDataSource.setSkipNumResults(true);
        
        actionsPanel.setActionsListener(this);
        actionsPanel.setSelectionListener(this);

        currentRowFields = new ArrayList<HeaderField>();
        currentColumnFields = new ArrayList<HeaderField>();

        for (FieldInfo fieldInfo : TkoUtils.getFieldList("group_fields")) {
            HeaderField field = new SimpleHeaderField(fieldInfo.name, fieldInfo.field);
            headerFieldMap.put(fieldInfo.field, field);
            rowSelect.addItem(field);
            columnSelect.addItem(field);
        }
        currentRowFields.add(headerFieldMap.get(DEFAULT_ROW));
        currentColumnFields.add(headerFieldMap.get(DEFAULT_COLUMN));
        updateWidgets();

        queryButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                doQuery();
                updateHistory();
            } 
        });
        
        spreadsheet.setVisible(false);
        spreadsheet.setListener(this);
        
        SimpleHyperlink swapLink = new SimpleHyperlink("swap");
        swapLink.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                List<HeaderField> newRows = columnSelect.getSelectedItems();
                setSelectedHeader(columnSelect, rowSelect.getSelectedItems());
                setSelectedHeader(rowSelect, newRows);
            } 
        });
        
        Panel filterOptions = new VerticalPanel();
        filterOptions.add(showIncomplete);
        filterOptions.add(showOnlyLatest);
        
        RootPanel.get("ss_filter_options").add(filterOptions);
        RootPanel.get("ss_row_select").add(rowSelect);
        RootPanel.get("ss_column_select").add(columnSelect);
        RootPanel.get("ss_swap").add(swapLink);
        RootPanel.get("ss_query_controls").add(queryButton);
        RootPanel.get("ss_actions").add(actionsPanel);
        RootPanel.get("ss_spreadsheet").add(spreadsheet);
        jobCompletionPanel = RootPanel.get("ss_job_completion");
        
        Window.addWindowResizeListener(new WindowResizeListener() {
            public void onWindowResized(int width, int height) {
                if(spreadsheet.isVisible())
                    spreadsheet.fillWindow(true);
            } 
        });
        
        setupDrilldownMap();
    }
    
    protected TestSet getWholeTableTestSet() {
        boolean isSingleTest = spreadsheetProcessor.getNumTotalTests() == 1;
        if (isSingleTest) {
            return getTestSet(spreadsheetProcessor.getLastCellInfo());
        }
        return new ConditionTestSet(getFullConditionArgs());
    }

    protected void setupDrilldownMap() {
        drilldownMap.put("platform", new String[] {"hostname", "test_name"});
        drilldownMap.put("hostname", new String[] {"job_tag", "status"});
        drilldownMap.put("job_tag", new String[] {"job_tag"});
        
        drilldownMap.put("kernel", new String[] {"test_name", "status"});
        drilldownMap.put("test_name", new String[] {"job_name", "job_tag"});
        
        drilldownMap.put("status", new String[] {"reason", "job_tag"});
        drilldownMap.put("reason", new String[] {"job_tag"});
        
        drilldownMap.put("job_owner", new String[] {"job_name", "job_tag"});
        drilldownMap.put("job_name", new String[] {"job_tag"});
        
        drilldownMap.put("test_finished_time", new String[] {"status", "job_tag"});
        drilldownMap.put("DATE(test_finished_time)", 
                         new String[] {"test_finished_time", "job_tag"});
    }
    
    protected void setSelectedHeader(HeaderSelect list, List<HeaderField> fields) {
        list.selectItems(fields);
    }

    @Override
    public void refresh() {
        notYetQueried = false;
        spreadsheet.setVisible(false);
        selectionManager.clearSelection();
        spreadsheet.clear();
        setJobCompletionHtml("&nbsp");
        
        final JSONObject condition = getFullConditionArgs();
        JSONObject queryParameters = getQueryParameters();
        
        setLoading(true);
        if (showOnlyLatest.isChecked()) {
            spreadsheetProcessor.setDataSource(latestDataSource);
        } else {
            spreadsheetProcessor.setDataSource(normalDataSource);
        }
        spreadsheetProcessor.setHeaders(currentRowFields, currentColumnFields, 
                                        getQueryParameters());
        spreadsheetProcessor.refresh(condition, new Command() {
            public void execute() {
                if (isJobFilteringCondition(condition)) {
                    showCompletionPercentage(condition);
                } else {
                    setLoading(false);
                }
            }
        });
    }

    private JSONObject getQueryParameters() {
        JSONObject parameters = new JSONObject();
        rowSelect.addQueryParameters(parameters);
        columnSelect.addQueryParameters(parameters);
        return parameters;
    }

    private JSONObject getFullConditionArgs() {
        JSONObject args = commonPanel.getSavedConditionArgs();
        String condition = TkoUtils.getSqlCondition(args);
        if (!condition.equals("")) {
            condition = "(" + condition + ") AND ";
        }
        condition += "status != 'TEST_NA'";
        if (!currentShowIncomplete) {
            condition += " AND status != 'RUNNING'";
        }
        args.put("extra_where", new JSONString(condition));
        return args;
    }

    public void doQuery() {
        List<HeaderField> rows = rowSelect.getSelectedItems();
        List<HeaderField> columns = columnSelect.getSelectedItems();
        if (rows.isEmpty() || columns.isEmpty()) {
            NotifyManager.getInstance().showError("You must select row and column fields");
            return;
        }
        if (!checkMachineLabelHeaders(rowSelect) || !checkMachineLabelHeaders(columnSelect)) {
            NotifyManager.getInstance().showError(
                      "You must enter labels for all machine label fields");
            return;
        }
        saveSelectedHeaders();
        currentShowIncomplete = showIncomplete.isChecked();
        commonPanel.saveSqlCondition();
        refresh();
    }

    private boolean checkMachineLabelHeaders(HeaderSelect headerSelect) {
        for (MachineLabelField field : headerSelect.getMachineLabelHeaders()) {
            if (field.getLabelList().isEmpty()) {
                return false;
            }
        }
        return true;
    }

    private void saveSelectedHeaders() {
        currentRowFields = rowSelect.getSelectedItems();
        currentColumnFields = columnSelect.getSelectedItems();
    }

    private void showCompletionPercentage(JSONObject condition) {
        rpcProxy.rpcCall("get_job_ids", condition, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                finishShowCompletionPercentage(result.isArray());
                setLoading(false);
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                setLoading(false);
            }
        });
    }

    private void finishShowCompletionPercentage(JSONArray jobIds) {
        final int jobCount = jobIds.size();
        if (jobCount == 0) {
            return;
        }
        
        JSONObject args = new JSONObject();
        args.put("job__id__in", jobIds);
        afeRpcProxy.rpcCall("get_hqe_percentage_complete", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                int percentage = (int) (result.isNumber().doubleValue() * 100);
                StringBuilder message = new StringBuilder("Matching ");
                if (jobCount == 1) {
                    message.append("job is ");
                } else {
                    message.append("jobs are ");
                }
                message.append(percentage);
                message.append("% complete");
                setJobCompletionHtml(message.toString());
            }
        });
    }
    
    private void setJobCompletionHtml(String html) {
        jobCompletionPanel.clear();
        jobCompletionPanel.add(new HTML(html));
    }

    private boolean isJobFilteringCondition(JSONObject condition) {
        return TkoUtils.getSqlCondition(condition).indexOf("job_tag") != -1;
    }

    public void onCellClicked(CellInfo cellInfo) {
        Event event = Event.getCurrentEvent();
        TestSet testSet = getTestSet(cellInfo);
        DrilldownType drilldownType = getDrilldownType(cellInfo);
        if (RightClickTable.isRightClick(event)) {
            if (!selectionManager.isEmpty()) {
                testSet = getTestSet(selectionManager.getSelectedCells());
                drilldownType = DrilldownType.DRILLDOWN_BOTH;
            }
            ContextMenu menu = getContextMenu(testSet, drilldownType);
            menu.showAtWindow(event.getClientX(), event.getClientY());
            return;
        }
        
        if (isSelectEvent(event)) {
            selectionManager.toggleSelected(cellInfo);
            return;
        }
        
        if (testSet.isSingleTest()) {
            listener.onSelectTest(testSet.getTestIndex());
            return;
        }
        
        doDrilldown(testSet, 
                    getDefaultDrilldownRow(drilldownType), 
                    getDefaultDrilldownColumn(drilldownType));
    }

    private DrilldownType getDrilldownType(CellInfo cellInfo) {
        if (cellInfo.row == null) {
            // column header
            return DrilldownType.DRILLDOWN_COLUMN;
        }
        if (cellInfo.column == null) {
            // row header
            return DrilldownType.DRILLDOWN_ROW;
        }
        return DrilldownType.DRILLDOWN_BOTH;
    }

    private TestSet getTestSet(CellInfo cellInfo) {
        boolean isSingleTest = cellInfo.testCount == 1;
        if (isSingleTest) {
            return new SingleTestSet(cellInfo.testIndex, getFullConditionArgs());
        }
        
        ConditionTestSet testSet = new ConditionTestSet(getFullConditionArgs());
        if (cellInfo.row != null) {
            setSomeFields(testSet, currentRowFields, cellInfo.row);
        }
        if (cellInfo.column != null) {
            setSomeFields(testSet, currentColumnFields, cellInfo.column);
        }
        return testSet;
    }
    
    private void setSomeFields(ConditionTestSet testSet, List<HeaderField> allFields, 
                               Header values) {
        for (int i = 0; i < values.size(); i++) {
            HeaderField field = allFields.get(i);
            String value = values.get(i);
            testSet.addCondition(field.getSqlCondition(value));
        }
    }
    
    private TestSet getTestSet(List<CellInfo> cells) {
        CompositeTestSet tests = new CompositeTestSet();
        for (CellInfo cell : cells) {
            tests.add(getTestSet(cell));
        }
        return tests;
    }

    private void doDrilldown(TestSet tests, String newRowField, String newColumnField) {
        commonPanel.refineCondition(tests);
        currentRowFields = Utils.wrapObjectWithList(headerFieldMap.get(newRowField));
        currentColumnFields = Utils.wrapObjectWithList(headerFieldMap.get(newColumnField));
        rowSelect.resetFixedValues();
        columnSelect.resetFixedValues();
        updateWidgets();
        doQuery();
        updateHistory();
    }

    private String getDefaultDrilldownRow(DrilldownType type) {
        return getDrilldownRows(type)[0];
    }
    
    private String getDefaultDrilldownColumn(DrilldownType type) {
        return getDrilldownColumns(type)[0];
    }

    private ContextMenu getContextMenu(final TestSet tests, DrilldownType drilldownType) {
        TestContextMenu menu = new TestContextMenu(tests, listener);
        
        if (!menu.addViewDetailsIfSingleTest()) {
            MenuBar drilldownMenu = menu.addSubMenuItem("Drill down");
            fillDrilldownMenu(tests, drilldownType, drilldownMenu);
        }
        
        menu.addItem("View in table", new Command() {
            public void execute() {
                switchToTable(tests, false);
            }
        });
        menu.addItem("Triage failures", new Command() {
            public void execute() {
                switchToTable(tests, true);
            }
        });
        
        menu.addLabelItems();
        return menu;
    }

    private void fillDrilldownMenu(final TestSet tests, DrilldownType drilldownType, MenuBar menu) {
        for (final String rowField : getDrilldownRows(drilldownType)) {
            for (final String columnField : getDrilldownColumns(drilldownType)) {
                if (rowField.equals(columnField)) {
                    continue;
                }
                menu.addItem(rowField + " vs. " + columnField, new Command() {
                    public void execute() {
                        doDrilldown(tests, rowField, columnField);
                    }
                });
            }
        }
    }

    private String[] getDrilldownFields(List<HeaderField> fields, DrilldownType type,
                                        DrilldownType otherType) {
        HeaderField lastField = fields.get(fields.size() - 1);
        String lastFieldName = lastField.getSqlName();
        if (type == otherType) {
            return new String[] {lastFieldName};
        } else {
            if (lastField instanceof MachineLabelField) {
                // treat machine label fields like platform, for the purpose of default drilldown
                lastFieldName = "platform";
            }
            return drilldownMap.get(lastFieldName);
        }
    }

    private String[] getDrilldownRows(DrilldownType type) {
        return getDrilldownFields(currentRowFields, type, DrilldownType.DRILLDOWN_COLUMN);
    }
    
    private String[] getDrilldownColumns(DrilldownType type) {
        return getDrilldownFields(currentColumnFields, type, DrilldownType.DRILLDOWN_ROW);
    }
    
    private void updateWidgets() {
        setSelectedHeader(rowSelect, currentRowFields);
        setSelectedHeader(columnSelect, currentColumnFields);
        showIncomplete.setChecked(currentShowIncomplete);
    }

    @Override
    protected Map<String, String> getHistoryArguments() {
        Map<String, String> arguments = super.getHistoryArguments();
        if (!notYetQueried) {
            rowSelect.addHistoryArguments(arguments, HISTORY_ROW);
            columnSelect.addHistoryArguments(arguments, HISTORY_COLUMN);
            arguments.put(HISTORY_SHOW_INCOMPLETE, Boolean.toString(currentShowIncomplete));
            arguments.put(HISTORY_ONLY_LATEST, Boolean.toString(showOnlyLatest.isChecked()));
            commonPanel.addHistoryArguments(arguments);
        }
        return arguments;
    }
    
    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        commonPanel.handleHistoryArguments(arguments);
        rowSelect.handleHistoryArguments(arguments, HISTORY_ROW);
        columnSelect.handleHistoryArguments(arguments, HISTORY_COLUMN);
        saveSelectedHeaders();
        
        currentShowIncomplete = Boolean.valueOf(arguments.get(HISTORY_SHOW_INCOMPLETE));
        showOnlyLatest.setChecked(Boolean.valueOf(arguments.get(HISTORY_ONLY_LATEST)));
        updateWidgets();
    }

    @Override
    protected void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, HISTORY_ROW, DEFAULT_ROW);
        Utils.setDefaultValue(arguments, HISTORY_COLUMN, DEFAULT_COLUMN);
        Utils.setDefaultValue(arguments, HISTORY_ROW + HeaderSelect.HISTORY_FIXED_VALUES, "");
        Utils.setDefaultValue(arguments, HISTORY_COLUMN + HeaderSelect.HISTORY_FIXED_VALUES, "");
        Utils.setDefaultValue(arguments, HISTORY_SHOW_INCOMPLETE, Boolean.toString(false));
        Utils.setDefaultValue(arguments, HISTORY_ONLY_LATEST, Boolean.toString(false));
    }

    private void switchToTable(final TestSet tests, boolean isTriageView) {
        commonPanel.refineCondition(tests);
        TableViewConfig config;
        if (isTriageView) {
            config = TableViewConfig.TRIAGE;
        } else {
            config = TableViewConfig.DEFAULT;
        }
        listener.onSwitchToTable(config);
    }

    public ContextMenu getActionMenu() {
        TestSet tests;
        if (selectionManager.isEmpty()) {
            tests = getWholeTableTestSet();
        } else {
            tests = getTestSet(selectionManager.getSelectedCells());
        }
        return getContextMenu(tests, DrilldownType.DRILLDOWN_BOTH);
    }

    public void onSelectAll(boolean ignored) {
        selectionManager.selectAll();
    }

    public void onSelectNone() {
        selectionManager.clearSelection();
    }

    @Override
    protected boolean hasFirstQueryOccurred() {
        return !notYetQueried;
    }

    private void setLoading(boolean loading) {
        queryButton.setEnabled(!loading);
        NotifyManager.getInstance().setLoading(loading);
    }

    public void onSetControlsVisible(boolean visible) {
        TkoUtils.setElementVisible("ss_all_controls", visible);
        if (isTabVisible()) {
            spreadsheet.fillWindow(true);
        }
    }
}
