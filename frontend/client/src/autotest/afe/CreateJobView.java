package autotest.afe;

import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.ui.NotifyManager;
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

public class CreateJobView extends TabView {
    public static final int TEST_COLUMNS = 5;
    
    // control file types
    protected static final String CLIENT_TYPE = "Client";
    protected static final String SERVER_TYPE = "Server";
    
    protected static final String EDIT_CONTROL_STRING = "Edit control file";
    protected static final String UNEDIT_CONTROL_STRING= "Revert changes";
    protected static final String VIEW_CONTROL_STRING = "View control file";
    protected static final String HIDE_CONTROL_STRING = "Hide control file";
    
    public interface JobCreateListener {
        public void onJobCreated(int jobId);
    }

    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected JobCreateListener listener;
    
    protected static class TestCheckBox extends CheckBox {
        protected int id;
        protected String testType, synchType;
        
        public TestCheckBox(JSONObject test) {
            super(test.get("name").isString().stringValue());
            id = (int) test.get("id").isNumber().doubleValue();
            testType = test.get("test_type").isString().stringValue();
            synchType = test.get("synch_type").isString().stringValue();
            String description = test.get("description").isString().stringValue();
            if (description.equals(""))
                description = "No description";
            setTitle(description);
        }
        
        public int getId() {
            return id;
        }

        public String getTestType() {
            return testType;
        }

        public String getSynchType() {
            return synchType;
        }
    }
    
    protected class CheckBoxPanel<T extends CheckBox> extends Composite {
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
            setEnabled(false);
        }
    }
    
    protected class TestPanel extends CheckBoxPanel<TestCheckBox> {
        String testType = null;
        
        public TestPanel(String testType, int columns) {
            super(columns);
            this.testType = testType;
        }
        
        public void addTest(TestCheckBox checkBox) {
            if (!checkBox.getTestType().equals(testType))
                throw new RuntimeException(
                    "Inconsistent test type for test " + checkBox.getText());
            super.add(checkBox);
        }
        
        @Override
        public void setEnabled(boolean enabled) {
            String synchType = null;
            List<TestCheckBox> checked = getChecked();
            if (!checked.isEmpty())
                synchType = checked.get(0).getSynchType();
            
            for(TestCheckBox thisBox : testBoxes) {
                boolean boxEnabled = enabled;
                if (enabled && synchType != null)
                    boxEnabled = thisBox.getSynchType().equals(synchType);
                thisBox.setEnabled(boxEnabled);
            }
        }
        
        public String getTestType() {
            return testType;
        }
    }
    
    protected static class ControlTypeSelect extends Composite {
        public static final String RADIO_GROUP = "controlTypeGroup";
        protected String clientType, serverType;
        protected RadioButton client, server;
        protected Panel panel = new HorizontalPanel();
        
        public ControlTypeSelect() {
            client = new RadioButton(RADIO_GROUP, CLIENT_TYPE);
            server = new RadioButton(RADIO_GROUP, SERVER_TYPE);
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
    protected TestPanel clientTestsPanel = new TestPanel(CLIENT_TYPE, TEST_COLUMNS), 
                        serverTestsPanel = new TestPanel(SERVER_TYPE, TEST_COLUMNS);
    protected CheckBoxPanel<CheckBox> profilersPanel = 
        new CheckBoxPanel<CheckBox>(TEST_COLUMNS);
    protected TextArea controlFile = new TextArea();
    protected DisclosurePanel controlFilePanel = new DisclosurePanel();
    protected ControlTypeSelect controlTypeSelect;
    protected CheckBox runSynchronous = new CheckBox("Synchronous");
    protected Button editControlButton = new Button(EDIT_CONTROL_STRING);
    protected HostSelector hostSelector;
    protected Button submitJobButton = new Button("Submit Job");
    
    protected boolean controlEdited = false;
    protected boolean controlReadyForSubmit = false;
    
    public CreateJobView(JobCreateListener listener) {
        this.listener = listener;
    }

    @Override
    public String getElementId() {
        return "create_job";
    }
    
    public void cloneJob(JSONValue cloneInfo) {
        reset();
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
        
        controlTypeSelect.setControlType(
                jobObject.get("control_type").isString().stringValue());
        runSynchronous.setChecked(
                jobObject.get("synch_type").isString().stringValue().equals("Synchronous"));
        controlFile.setText(
                jobObject.get("control_file").isString().stringValue());
        controlReadyForSubmit = true;
        
        JSONArray hostInfo = cloneObject.get("hosts").isArray();
        for (int i = 0; i < hostInfo.size(); i++) {
            JSONObject host = hostInfo.get(i).isObject();
            
            host.put("locked_text", AfeUtils.getLockedText(host));
        }
        
        hostSelector.availableSelection.selectObjects(new JSONArrayList<JSONObject>(hostInfo));
        
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
        runSynchronous.setEnabled(true);
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
    
    protected void populateTests() {
        JSONArray tests = staticData.getData("tests").isArray();
        
        for(int i = 0; i < tests.size(); i++) {
            JSONObject test = tests.get(i).isObject();
            TestCheckBox checkbox = new TestCheckBox(test);
            checkbox.addClickListener(new ClickListener() {
                public void onClick(Widget sender) {
                    generateControlFile(false);
                    setInputsEnabled();
                }
            });
            String type = test.get("test_type").isString().stringValue();
            if (type.equals("Client"))
                clientTestsPanel.addTest(checkbox);
            else if (type.equals("Server"))
                serverTestsPanel.addTest(checkbox);
            else
                throw new RuntimeException("Invalid control type: " + type);
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
    
    protected JSONObject getControlFileParams(boolean readyForSubmit) {
        JSONObject params = new JSONObject();
        JSONArray tests = new JSONArray(), profilers = new JSONArray();
        List<TestCheckBox> checkedTests = serverTestsPanel.getChecked();
        if (checkedTests.isEmpty()) {
            checkedTests = clientTestsPanel.getChecked();
        }
        List<CheckBox> checkedProfilers = profilersPanel.getChecked();
        String kernelString = kernel.getText();
        if (!kernelString.equals("")) {
            params.put("kernel", new JSONString(kernelString));
        }
        
        int i = 0;
        for (TestCheckBox test : checkedTests) {
            tests.set(i++, new JSONNumber(test.getId()));
        }
        
        i = 0;
        for (CheckBox profiler : checkedProfilers) {
            profilers.set(i++, new JSONString(profiler.getText()));
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
                JSONArray results = result.isArray();
                String controlFileText = results.get(0).isString().stringValue();
                boolean isServer = results.get(1).isBoolean().booleanValue();
                boolean isSynchronous = results.get(2).isBoolean().booleanValue();
                controlFile.setText(controlFileText);
                controlTypeSelect.setControlType(isServer ? 
                                                serverTestsPanel.getTestType() : 
                                                clientTestsPanel.getTestType());
                runSynchronous.setChecked(isSynchronous);
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
    
    protected void setInputsEnabled() {
        if (!clientTestsPanel.getChecked().isEmpty()) {
            clientTestsPanel.setEnabled(true);
            profilersPanel.setEnabled(true);
            serverTestsPanel.setEnabled(false);
        }
        else if (!serverTestsPanel.getChecked().isEmpty()) {
            clientTestsPanel.setEnabled(false);
            profilersPanel.setEnabled(false);
            serverTestsPanel.setEnabled(true);
        }
        else {
            clientTestsPanel.setEnabled(true);
            profilersPanel.setEnabled(true);
            serverTestsPanel.setEnabled(true);
        }

        kernel.setEnabled(true);
        timeout.setEnabled(true);
    }
    
    protected void disableInputs() {
        clientTestsPanel.setEnabled(false);
        serverTestsPanel.setEnabled(false);
        profilersPanel.setEnabled(false);
        kernel.setEnabled(false);
    }
    
    @Override
    public void initialize() {
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

        populateTests();
        populatePriorities();
        
        controlFile.setSize("50em", "30em");
        controlTypeSelect = new ControlTypeSelect();
        Panel controlOptionsPanel = new HorizontalPanel();
        controlOptionsPanel.add(controlTypeSelect);
        controlOptionsPanel.add(runSynchronous);
        runSynchronous.addStyleName("extra-space-left");
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
                    runSynchronous.setEnabled(false);
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
                submitJob();
            }
        });
        
        reset();
        
        RootPanel.get("create_job_name").add(jobName);
        RootPanel.get("create_kernel").add(kernel);
        RootPanel.get("create_timeout").add(timeout);
        RootPanel.get("create_priority").add(priorityList);
        RootPanel.get("create_client_tests").add(clientTestsPanel);
        RootPanel.get("create_server_tests").add(serverTestsPanel);
        RootPanel.get("create_profilers").add(profilersPanel);
        RootPanel.get("create_edit_control").add(controlFilePanel);
        RootPanel.get("create_submit").add(submitJobButton);
    }
    
    public void reset() {
        jobName.setText("");
        resetPriorityToDefault();
        kernel.setText("");
        timeout.setText(StaticDataRepository.getRepository().
            getData("job_timeout_default").isString().stringValue());
        clientTestsPanel.reset();
        serverTestsPanel.reset();
        profilersPanel.reset();
        setInputsEnabled();
        controlTypeSelect.setControlType(clientTestsPanel.getTestType());
        controlTypeSelect.setEnabled(false);
        runSynchronous.setEnabled(false);
        runSynchronous.setChecked(false);
        controlFile.setText("");
        controlFile.setReadOnly(true);
        controlEdited = false;
        editControlButton.setText(EDIT_CONTROL_STRING);
        hostSelector.reset();
    }
    
    protected void submitJob() {
        // Read and validate the timeout
        String timeoutString = timeout.getText();
        final int timeoutInt;
        try {
            if (timeoutString.equals("") ||
                (timeoutInt = Integer.parseInt(timeoutString)) <= 0) {
                    String error = "Please enter a positive timeout";
                    NotifyManager.getInstance().showError(error);
                    return;
            }
        } catch (NumberFormatException e) {
            String error = "Invalid timeout " + timeoutString;
            NotifyManager.getInstance().showError(error);
            return;
        }
      
        // disallow accidentally clicking submit twice
        submitJobButton.setEnabled(false);
        
        final SimpleCallback doSubmit = new SimpleCallback() {
            public void doCallback(Object source) {
                JSONObject args = new JSONObject();
                args.put("name", new JSONString(jobName.getText()));
                String priority = priorityList.getItemText(
                                               priorityList.getSelectedIndex());
                args.put("priority", new JSONString(priority));
                args.put("control_file", new JSONString(controlFile.getText()));
                args.put("control_type", 
                         new JSONString(controlTypeSelect.getControlType()));
                args.put("is_synchronous", 
                         JSONBoolean.getInstance(runSynchronous.isChecked()));
                args.put("timeout", new JSONNumber(timeoutInt));
                
                HostSelector.HostSelection hosts = hostSelector.getSelectedHosts();
                args.put("hosts", Utils.stringsToJSON(hosts.hosts));
                args.put("meta_hosts", Utils.stringsToJSON(hosts.metaHosts));
                
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
    
    @Override
    public void refresh() {
        super.refresh();
        hostSelector.refresh();
    }
}
