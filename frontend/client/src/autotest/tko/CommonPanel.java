package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.ElementWidget;
import autotest.common.ui.SimpleHyperlink;
import autotest.tko.TkoUtils.FieldInfo;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.PopupPanel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;
import com.google.gwt.user.client.ui.PopupPanel.PositionCallback;

import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

class CommonPanel extends Composite implements ClickListener, PositionCallback {
    private static final String SHOW_QUICK_REFERENCE = "Show quick reference";
    private static final String HIDE_QUICK_REFERENCE = "Hide quick reference";
    private static final String SHOW_CONTROLS = "Show controls";
    private static final String HIDE_CONTROLS = "Hide controls";
    private static CommonPanel theInstance = new CommonPanel();
    
    private TextArea customSqlBox = new TextArea();
    private CheckBox showInvalid = new CheckBox("Show invalidated tests");
    private SimpleHyperlink quickReferenceLink = new SimpleHyperlink(SHOW_QUICK_REFERENCE);
    private PopupPanel quickReferencePopup;
    private SimpleHyperlink showHideControlsLink = new SimpleHyperlink(HIDE_CONTROLS);
    private Panel allControlsPanel = RootPanel.get("common_all_controls");
    private String currentCondition = "";
    private boolean currentShowInvalid = false;
    private Set<CommonPanelListener> listeners = new HashSet<CommonPanelListener>();
    
    public static interface CommonPanelListener {
        public void onSetControlsVisible(boolean visible);
    }
    
    private CommonPanel() {
        ElementWidget panelElement = new ElementWidget("common_panel");
        initWidget(panelElement);
    }
    
    public void initialize() {
        customSqlBox.setSize("50em", "5em");
        quickReferenceLink.addClickListener(this);
        showHideControlsLink.addClickListener(this);
        
        Panel commonFilterPanel = new VerticalPanel();
        commonFilterPanel.add(customSqlBox);
        commonFilterPanel.add(showInvalid);
        RootPanel.get("common_filters").add(commonFilterPanel);
        RootPanel.get("common_quick_reference").add(quickReferenceLink);
        RootPanel.get("common_show_hide_controls").add(showHideControlsLink);
        generateQuickReferencePopup();
    }
    
    public static CommonPanel getPanel() {
        return theInstance;
    }
    
    /**
     * For testability.
     */
    public static void setInstance(CommonPanel panel) {
        theInstance = panel;
    }
    
    public void setConditionVisible(boolean visible) {
        RootPanel.get("common_condition_div").setVisible(visible);
    }
    
    private String getSqlCondition() {
        return customSqlBox.getText().trim();
    }
    
    private void setSqlCondition(String text) {
        customSqlBox.setText(text);
        saveSqlCondition();
    }
    
    public void saveSqlCondition() {
        currentCondition = getSqlCondition();
        currentShowInvalid = showInvalid.isChecked();
    }
    
    public JSONObject getSavedConditionArgs() {
        JSONObject args = new JSONObject();
        args.put("extra_where", new JSONString(currentCondition));
        if (!currentShowInvalid) {
            List<String> labelsToExclude = Arrays.asList(new String[] {"invalidated"});
            args.put("exclude_labels", Utils.stringsToJSON(labelsToExclude));
        }
        return args;
    }

    public void setCondition(TestSet tests) {
        setSqlCondition(tests.getCondition());
    }

    public void handleHistoryArguments(Map<String, String> arguments) {
        setSqlCondition(arguments.get("condition"));
        currentShowInvalid = Boolean.valueOf(arguments.get("show_invalid"));
        showInvalid.setChecked(currentShowInvalid);
    }
    
    public void addHistoryArguments(Map<String, String> arguments) {
        arguments.put("condition", currentCondition);
        arguments.put("show_invalid", Boolean.toString(currentShowInvalid));
    }

    public void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, "condition", "");
        Utils.setDefaultValue(arguments, "show_invalid", Boolean.toString(currentShowInvalid));
    }

    public void onClick(Widget sender) {
        if (sender == quickReferenceLink) {
            handleQuickReferenceClick();
        } else {
            assert sender == showHideControlsLink;
            handleShowHideControlsClick();
        }
    }

    private void handleShowHideControlsClick() {
        boolean areControlsVisible = showHideControlsLink.getText().equals(SHOW_CONTROLS);
        allControlsPanel.setVisible(areControlsVisible);
        showHideControlsLink.setText(areControlsVisible ? HIDE_CONTROLS : SHOW_CONTROLS);
        for (CommonPanelListener listener : listeners) {
            listener.onSetControlsVisible(areControlsVisible);
        }
    }

    private void handleQuickReferenceClick() {
        if (isQuickReferenceShowing()) {
            quickReferencePopup.hide();
            quickReferenceLink.setText(SHOW_QUICK_REFERENCE);
        } else {
            quickReferencePopup.setPopupPositionAndShow(this);
            quickReferenceLink.setText(HIDE_QUICK_REFERENCE);
        }
    }

    private boolean isQuickReferenceShowing() {
        return quickReferenceLink.getText().equals(HIDE_QUICK_REFERENCE);
    }

    private void generateQuickReferencePopup() {
        FlexTable fieldTable = new FlexTable();
        fieldTable.setText(0, 0, "Name");
        fieldTable.setText(0, 1, "Field");
        fieldTable.getRowFormatter().setStyleName(0, "data-row-header");
        int row = 1;
        for (FieldInfo fieldInfo : TkoUtils.getFieldList("all_fields")) {
            fieldTable.setText(row, 0, fieldInfo.name);
            fieldTable.setText(row, 1, fieldInfo.field);
            row++;
        }
        quickReferencePopup = new PopupPanel(false);
        quickReferencePopup.add(fieldTable);
    }

    /**
     * PopupListener callback.
     */
    public void setPosition(int offsetWidth, int offsetHeight) {
        quickReferencePopup.setPopupPosition(
             customSqlBox.getAbsoluteLeft() + customSqlBox.getOffsetWidth(), 
             customSqlBox.getAbsoluteTop());
    }
    
    public void addListener(CommonPanelListener listener) {
        listeners.add(listener);
    }
}
