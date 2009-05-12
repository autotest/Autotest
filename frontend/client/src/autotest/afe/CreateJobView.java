package autotest.afe;

import autotest.afe.TestSelector.TestSelectorListener;
import autotest.afe.UserPreferencesView.UserPreferencesListener;
import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RadioChooser;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.TabView;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DisclosureEvent;
import com.google.gwt.user.client.ui.DisclosureHandler;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.FocusListener;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Hyperlink;
import com.google.gwt.user.client.ui.KeyboardListener;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RadioButton;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.List;

public class CreateJobView extends TabView 
                           implements TestSelectorListener, UserPreferencesListener {
    public static final int TEST_COLUMNS = 5;
    
    protected static final String EDIT_CONTROL_STRING = "Edit control file";
    protected static final String UNEDIT_CONTROL_STRING= "Revert changes";
    protected static final String VIEW_CONTROL_STRING = "View control file";
    protected static final String HIDE_CONTROL_STRING = "Hide control file";
    
    public interface JobCreateListener {
        public void onJobCreated(int jobId);
    }

    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected JobCreateListener listener;
    
    private static class CheckBoxPanel<T extends CheckBox> extends Composite {
        protected int numColumns;
        protected FlexTable table = new FlexTable();
        protected List<T> testBoxes = new ArrayList<T>();
        
        public CheckBoxPanel(int columns) {
            numColumns = columns;
            initWidget(table);
        }
        
        public void add(T checkBox) {
            int row = testBoxes.size() / numColumns;
            int col = testBoxes.size() % numColumns;
            table.setWidget(row, col, checkBox);
            testBoxes.add(checkBox);
        }

        public List<T> getChecked() {
            List<T> result = new ArrayList<T>();
            for(T checkBox : testBoxes) {
                if (checkBox.isChecked())
                    result.add(checkBox);
            }
            return result;
        }

        public void setEnabled(boolean enabled) {
            for(T thisBox : testBoxes) {
                thisBox.setEnabled(enabled);
            }
        }

        public void reset() {
            for (T thisBox : testBoxes) {
                thisBox.setChecked(false);
            }
        }
    }
    
    private static class ControlTypeSelect extends Composite {
        public static final String RADIO_GROUP = "controlTypeGroup";
        protected RadioButton client, server;
        protected Panel panel = new HorizontalPanel();
        
        public ControlTypeSelect() {
            client = new RadioButton(RADIO_GROUP, TestSelector.CLIENT_TYPE);
            server = new RadioButton(RADIO_GROUP, TestSelector.SERVER_TYPE);
            panel.add(client);
            panel.add(server);
            client.setChecked(true); // client is default
            initWidget(panel);
            
            client.addClickListener(new ClickListener() {
                public void onClick(Widget sender) {
                    onChanged();
                }
            });
            server.addClickListener(new ClickListener() {
                public void onClick(Widget sender) {
                    onChanged();
                }
            });
        }
        
        public String getControlType() {
            if (client.isChecked())
                return client.getText();
            return server.getText();
        }
        
        public void setControlType(String type) {
            if (client.getText().equals(type))
                client.setChecked(true);
            else if (server.getText().equals(type))
                server.setChecked(true);
            else
                throw new IllegalArgumentException("Invalid control type");
            onChanged();
        }
        
        public void setEnabled(boolean enabled) {
            client.setEnabled(enabled);
            server.setEnabled(enabled);
        }
        
        protected void onChanged() {
        }
    }
    
    protected StaticDataRepository staticData = StaticDataRepository.getRepository();
    
    protected TextBox jobName = new TextBox();
    protected ListBox priorityList = new ListBox();
    protected TextBox kernel = new TextBox();
    protected TextBox timeout = new TextBox();
    protected TextBox emailList = new TextBox();
    protected CheckBox skipVerify = new CheckBox();
    private RadioChooser rebootBefore = new RadioChooser();
    private RadioChooser rebootAfter = new RadioChooser();
    private CheckBox parseFailedRepair = new CheckBox();
    protected TestSelector testSelector;
    protected CheckBoxPanel<CheckBox> profilersPanel = 
        new CheckBoxPanel<CheckBox>(TEST_COLUMNS);
    protected TextArea controlFile = new TextArea();
    protected DisclosurePanel controlFilePanel = new DisclosurePanel();
    protected ControlTypeSelect controlTypeSelect;
    protected TextBox synchCountInput = new TextBox();
    protected Button editControlButton = new Button(EDIT_CONTROL_STRING);
    protected HostSelector hostSelector;
    protected Button submitJobButton = new Button("Submit Job");
    protected Button createTemplateJobButton = new Button("Create Template Job");
    private Button resetButton = new Button("Reset");
    
    protected boolean controlEdited = false;
    protected boolean controlReadyForSubmit = false;
    private JSONArray dependencies = new JSONArray();
    
    public CreateJobView(JobCreateListener listener) {
        this.listener = listener;
    }

    @Override
    public String getElementId() {
        return "create_job";
    }
    
    public void cloneJob(JSONValue cloneInfo) {
        // reset() fires the TestSelectorListener, which will generate a new control file. We do
        // no want this, so we'll stop listening to it for a bit.
        testSelector.setListener(null);
        reset();
        testSelector.setListener(this);
        
        disableInputs();
        openControlFileEditor();
        JSONObject cloneObject = cloneInfo.isObject();
        JSONObject jobObject = cloneObject.get("job").isObject();
        
        jobName.setText(jobObject.get("name").isString().stringValue());
        
        String priority = jobObject.get("priority").isString().stringValue();
        for (int i = 0; i < priorityList.getItemCount(); i++) {
            if (priorityList.getItemText(i).equals(priority)) {
                priorityList.setSelectedIndex(i);
                break;
            }
        }
        
        timeout.setText(Integer.toString(
                (int) jobObject.get("timeout").isNumber().doubleValue()));
        emailList.setText(
                jobObject.get("email_list").isString().stringValue());

        skipVerify.setChecked(!jobObject.get("run_verify").isBoolean().booleanValue());
        rebootBefore.setSelectedChoice(Utils.jsonToString(jobObject.get("reboot_before")));
        rebootAfter.setSelectedChoice(Utils.jsonToString(jobObject.get("reboot_after")));
        parseFailedRepair.setChecked(
                jobObject.get("parse_failed_repair").isBoolean().booleanValue());

        controlTypeSelect.setControlType(
                jobObject.get("control_type").isString().stringValue());
        synchCountInput.setText(Utils.jsonToString(jobObject.get("synch_count")));
        setSelectedDependencies(jobObject.get("dependencies").isArray());
        controlFile.setText(
                jobObject.get("control_file").isString().stringValue());
        controlReadyForSubmit = true;
        
        JSONArray hostInfo = cloneObject.get("hosts").isArray();
        List<JSONObject> hosts = new JSONArrayList<JSONObject>(hostInfo);
        for (JSONObject host : hosts) {
            // One-time hosts will already have the locked_text field set by the RPC. Other hosts
            // will need to create their locked_text fields.
            if (host.get("locked_text") == null) {
                host.put("locked_text", AfeUtils.getLockedText(host));
            }
        }
        hostSelector.availableSelection.selectObjects(hosts);
        
        JSONObject metaHostCounts = cloneObject.get("meta_host_counts").isObject();
        
        for (String label : metaHostCounts.keySet()) {
            String number = Integer.toString(
                (int) metaHostCounts.get(label).isNumber().doubleValue());
            hostSelector.selectMetaHost(label, number);
        }
        
        hostSelector.refresh();
    }
    
    protected void openControlFileEditor() {
        controlFile.setReadOnly(false);
        editControlButton.setText(UNEDIT_CONTROL_STRING);
        controlFilePanel.setOpen(true);
        controlTypeSelect.setEnabled(true);
        synchCountInput.setEnabled(true);
        editControlButton.setEnabled(true);
    }
    
    protected void populatePriorities(JSONArray priorities) {
        for(int i = 0; i < priorities.size(); i++) {
            JSONArray priorityData = priorities.get(i).isArray();
            String priority = priorityData.get(1).isString().stringValue();
            priorityList.addItem(priority);
        }
        
        resetPriorityToDefault();
    }
    
    protected void resetPriorityToDefault() {
        JSONValue defaultValue = staticData.getData("default_priority");
        String defaultPriority = defaultValue.isString().stringValue();
        for(int i = 0; i < priorityList.getItemCount(); i++) {
            if (priorityList.getItemText(i).equals(defaultPriority))
                priorityList.setSelectedIndex(i);
        }
    }
    
    protected void populatePriorities() {
        JSONArray tests = staticData.getData("profilers").isArray();
        
        for(JSONObject profiler : new JSONArrayList<JSONObject>(tests)) {
            String name = profiler.get("name").isString().stringValue();
            CheckBox checkbox = new CheckBox(name);
            checkbox.addClickListener(new ClickListener() {
                public void onClick(Widget sender) {
                    generateControlFile(false);
                    setInputsEnabled();
                }
            });
            profilersPanel.add(checkbox);
        }
    }
    
    private void populateRebootChoices() {
        AfeUtils.populateRadioChooser(rebootBefore, "reboot_before");
        AfeUtils.populateRadioChooser(rebootAfter, "reboot_after");
    }

    /**
     * Get parameters to submit to the generate_control_file RPC.
     * @param readyForSubmit are we getting a control file that's ready to submit for a job, or just
     * an intermediate control file to be viewed by the user?
     */
    protected JSONObject getControlFileParams(boolean readyForSubmit) {
        JSONObject params = new JSONObject();
        
        String kernelString = kernel.getText();
        if (!kernelString.equals("")) {
            params.put("kernel", new JSONString(kernelString));
        }
        
        JSONArray tests = new JSONArray();
        for (JSONObject test : testSelector.getSelectedTests()) {
            tests.set(tests.size(), test.get("id"));
        }
        
        JSONArray profilers = new JSONArray();
        for (CheckBox profiler : profilersPanel.getChecked()) {
            profilers.set(profilers.size(), new JSONString(profiler.getText()));
        }
        
        params.put("tests", tests);
        params.put("profilers", profilers);
        return params;
    }
    
    protected void generateControlFile(final boolean readyForSubmit, 
                                       final SimpleCallback finishedCallback,
                                       final SimpleCallback errorCallback) {
        JSONObject params = getControlFileParams(readyForSubmit);
        rpcProxy.rpcCall("generate_control_file", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONObject controlInfo = result.isObject();
                String controlFileText = controlInfo.get("control_file").isString().stringValue();
                boolean isServer = controlInfo.get("is_server").isBoolean().booleanValue();
                String synchCount = Utils.jsonToString(controlInfo.get("synch_count"));
                setSelectedDependencies(controlInfo.get("dependencies").isArray());
                controlFile.setText(controlFileText);
                controlTypeSelect.setControlType(isServer ? TestSelector.SERVER_TYPE : 
                                                            TestSelector.CLIENT_TYPE);
                synchCountInput.setText(synchCount);
                controlReadyForSubmit = readyForSubmit;
                if (finishedCallback != null)
                    finishedCallback.doCallback(this);
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                if (errorCallback != null)
                    errorCallback.doCallback(this);
            }
        });
    }

    protected void generateControlFile(boolean readyForSubmit) {
        generateControlFile(readyForSubmit, null, null);
    }
    
    public void handleSkipVerify() {
        boolean shouldSkipVerify = false;
        for (JSONObject test : testSelector.getSelectedTests()) {
            boolean runVerify = test.get("run_verify").isBoolean().booleanValue();
            if (!runVerify) {
                shouldSkipVerify = true;
                break;
            }
        }
        
        if (shouldSkipVerify) {
            skipVerify.setChecked(true);
            skipVerify.setEnabled(false);
        } else {
            skipVerify.setEnabled(true);
        }
    }
    
    protected void setInputsEnabled() {
        testSelector.setEnabled(true);
        profilersPanel.setEnabled(true);
        handleSkipVerify();
        kernel.setEnabled(true);
    }

    protected  boolean isClientTypeSelected() {
        return testSelector.getSelectedTestType().equals(TestSelector.CLIENT_TYPE);
    }
    
    protected void disableInputs() {
        testSelector.setEnabled(false);
        profilersPanel.setEnabled(false);
        kernel.setEnabled(false);
    }
    
    @Override
    public void initialize() {
        super.initialize();
        populatePriorities(staticData.getData("priorities").isArray());
        
        kernel.addFocusListener(new FocusListener() {
            public void onFocus(Widget sender) {}
            public void onLostFocus(Widget sender) {
                generateControlFile(false);
            }
        });
        kernel.addKeyboardListener(new KeyboardListener() {
            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {}
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {
                if (keyCode == KEY_ENTER)
                    generateControlFile(false);
            }
        });

        populatePriorities();
        
        testSelector = new TestSelector();
        
        populateRebootChoices();
        onPreferencesChanged();
        
        controlFile.setSize("50em", "30em");
        controlTypeSelect = new ControlTypeSelect();
        HorizontalPanel controlOptionsPanel = new HorizontalPanel();
        controlOptionsPanel.setVerticalAlignment(HorizontalPanel.ALIGN_BOTTOM);
        controlOptionsPanel.add(controlTypeSelect);
        Label useLabel = new Label("Use");
        useLabel.getElement().getStyle().setProperty("marginLeft", "1em");
        synchCountInput.setSize("3em", ""); // set width only
        synchCountInput.getElement().getStyle().setProperty("margin", "0 0.5em 0 0.5em");
        controlOptionsPanel.add(useLabel);
        controlOptionsPanel.add(synchCountInput);
        controlOptionsPanel.add(new Label("host(s) per execution"));
        Panel controlEditPanel = new VerticalPanel();
        controlEditPanel.add(controlOptionsPanel);
        controlEditPanel.add(controlFile);
        
        Panel controlHeaderPanel = new HorizontalPanel();
        final Hyperlink viewLink = new SimpleHyperlink(VIEW_CONTROL_STRING);
        controlHeaderPanel.add(viewLink);
        controlHeaderPanel.add(editControlButton);
        
        controlFilePanel.setHeader(controlHeaderPanel);
        controlFilePanel.add(controlEditPanel);
        
        editControlButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                DOM.eventCancelBubble(DOM.eventGetCurrentEvent(), true);
                
                if (editControlButton.getText().equals(EDIT_CONTROL_STRING)) {
                    disableInputs();
                    editControlButton.setEnabled(false);
                    SimpleCallback onGotControlFile = new SimpleCallback() {
                        public void doCallback(Object source) {
                            openControlFileEditor();
                        }
                    };
                    SimpleCallback onControlFileError = new SimpleCallback() {
                        public void doCallback(Object source) {
                            setInputsEnabled();
                            editControlButton.setEnabled(true);
                        }
                    };
                    generateControlFile(true, onGotControlFile, onControlFileError);
                }
                else {
                    if (controlEdited && 
                        !Window.confirm("Are you sure you want to revert your" +
                                        " changes?"))
                        return;
                    generateControlFile(false);
                    controlFile.setReadOnly(true);
                    setInputsEnabled();
                    editControlButton.setText(EDIT_CONTROL_STRING);
                    controlTypeSelect.setEnabled(false);
                    synchCountInput.setEnabled(false);
                    controlEdited = false;
                }
            }
        });
        
        controlFile.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
                controlEdited = true;
            } 
        });
        
        controlFilePanel.addEventHandler(new DisclosureHandler() {
            public void onClose(DisclosureEvent event) {
                viewLink.setText(VIEW_CONTROL_STRING);
            }

            public void onOpen(DisclosureEvent event) {
                viewLink.setText(HIDE_CONTROL_STRING);
            }
        });
        
        hostSelector = new HostSelector();
        
        submitJobButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                submitJob(false);
            }
        });
        
        createTemplateJobButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                submitJob(true);
            }
        });
        
        resetButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                reset();
            }
        });
        
        reset();
        
        RootPanel.get("create_job_name").add(jobName);
        RootPanel.get("create_kernel").add(kernel);
        RootPanel.get("create_timeout").add(timeout);
        RootPanel.get("create_email_list").add(emailList);
        RootPanel.get("create_priority").add(priorityList);
        RootPanel.get("create_skip_verify").add(skipVerify);
        RootPanel.get("create_reboot_before").add(rebootBefore);
        RootPanel.get("create_reboot_after").add(rebootAfter);
        RootPanel.get("create_parse_failed_repair").add(parseFailedRepair);
        RootPanel.get("create_tests").add(testSelector);
        RootPanel.get("create_profilers").add(profilersPanel);
        RootPanel.get("create_edit_control").add(controlFilePanel);
        RootPanel.get("create_submit").add(submitJobButton);
        RootPanel.get("create_template_job").add(createTemplateJobButton);
        RootPanel.get("create_reset").add(resetButton);
        
        testSelector.setListener(this);
    }

    public void reset() {
        StaticDataRepository repository = StaticDataRepository.getRepository();

        jobName.setText("");
        resetPriorityToDefault();
        rebootBefore.reset();
        rebootAfter.reset();
        parseFailedRepair.setChecked(
                repository.getData("parse_failed_repair_default").isBoolean().booleanValue());
        kernel.setText("");        
        timeout.setText(repository.getData("job_timeout_default").isString().stringValue());
        emailList.setText("");
        testSelector.reset();
        skipVerify.setChecked(false);
        profilersPanel.reset();
        setInputsEnabled();
        controlTypeSelect.setControlType(TestSelector.CLIENT_TYPE);
        controlTypeSelect.setEnabled(false);
        synchCountInput.setEnabled(false);
        synchCountInput.setText("1");
        controlFile.setText("");
        controlFile.setReadOnly(true);
        controlEdited = false;
        controlFilePanel.setOpen(false);
        editControlButton.setText(EDIT_CONTROL_STRING);
        hostSelector.reset();
        dependencies = new JSONArray();
    }
    
    protected void submitJob(final boolean isTemplate) {
        final int timeoutValue, synchCount;
        try {
            timeoutValue = parsePositiveIntegerInput(timeout.getText(), "timeout");
            synchCount = parsePositiveIntegerInput(synchCountInput.getText(), 
                                                   "number of machines used per execution");
        } catch (IllegalArgumentException exc) {
            return;
        }
      
        // disallow accidentally clicking submit twice
        submitJobButton.setEnabled(false);
        
        final SimpleCallback doSubmit = new SimpleCallback() {
            public void doCallback(Object source) {
                JSONObject args = new JSONObject();
                args.put("name", new JSONString(jobName.getText()));
                String priority = priorityList.getItemText(priorityList.getSelectedIndex());
                args.put("priority", new JSONString(priority));
                args.put("control_file", new JSONString(controlFile.getText()));
                args.put("control_type", 
                         new JSONString(controlTypeSelect.getControlType()));
                args.put("synch_count", new JSONNumber(synchCount));
                args.put("timeout", new JSONNumber(timeoutValue));
                args.put("email_list", new JSONString(emailList.getText()));
                args.put("run_verify", JSONBoolean.getInstance(!skipVerify.isChecked()));
                args.put("is_template", JSONBoolean.getInstance(isTemplate));
                args.put("dependencies", getSelectedDependencies());
                args.put("reboot_before", new JSONString(rebootBefore.getSelectedChoice()));
                args.put("reboot_after", new JSONString(rebootAfter.getSelectedChoice()));
                args.put("parse_failed_repair",
                         JSONBoolean.getInstance(parseFailedRepair.isChecked()));

                HostSelector.HostSelection hosts = hostSelector.getSelectedHosts();
                args.put("hosts", Utils.stringsToJSON(hosts.hosts));
                args.put("meta_hosts", Utils.stringsToJSON(hosts.metaHosts));
                args.put("one_time_hosts",
                    Utils.stringsToJSON(hosts.oneTimeHosts));

                rpcProxy.rpcCall("create_job", args, new JsonRpcCallback() {
                    @Override
                    public void onSuccess(JSONValue result) {
                        int id = (int) result.isNumber().doubleValue();
                        NotifyManager.getInstance().showMessage(
                                    "Job " + Integer.toString(id) + " created");
                        reset();
                        if (listener != null)
                            listener.onJobCreated(id);
                        submitJobButton.setEnabled(true);
                    }

                    @Override
                    public void onError(JSONObject errorObject) {
                        super.onError(errorObject);
                        submitJobButton.setEnabled(true);
                    }
                });
            }
        };
        
        // ensure control file is ready for submission
        if (!controlReadyForSubmit)
            generateControlFile(true, doSubmit, new SimpleCallback() {
                public void doCallback(Object source) {
                    submitJobButton.setEnabled(true);
                }
            });
        else
            doSubmit.doCallback(this);
    }

    private JSONArray getSelectedDependencies() {
        return dependencies;
    }

    private void setSelectedDependencies(JSONArray dependencies) {
        this.dependencies = dependencies;
    }

    private int parsePositiveIntegerInput(String input, String fieldName) {
        final int parsedInt;
        try {
            if (input.equals("") ||
                (parsedInt = Integer.parseInt(input)) <= 0) {
                    String error = "Please enter a positive " + fieldName;
                    NotifyManager.getInstance().showError(error);
                    throw new IllegalArgumentException();
            }
        } catch (NumberFormatException e) {
            String error = "Invalid " + fieldName + ": \"" + input + "\"";
            NotifyManager.getInstance().showError(error);
            throw new IllegalArgumentException();
        }
        return parsedInt;
    }
    
    @Override
    public void refresh() {
        super.refresh();
        hostSelector.refresh();
    }

    public void onTestSelectionChanged() {
        generateControlFile(false);
        setInputsEnabled();
    }
    
    private void setRebootSelectorDefault(RadioChooser chooser, String name) {
        JSONObject user = staticData.getData("current_user").isObject();
        String defaultOption = Utils.jsonToString(user.get(name));
        chooser.setDefaultChoice(defaultOption);
    }

    public void onPreferencesChanged() {
        setRebootSelectorDefault(rebootBefore, "reboot_before");
        setRebootSelectorDefault(rebootAfter, "reboot_after");
        testSelector.reset();
    }
}
