package afeclient.client;

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
import java.util.Iterator;
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
    
    protected class TestCheckBox extends CheckBox {
        protected int id;
        protected String testType, synchType;
        
        public TestCheckBox(JSONObject test) {
            super(test.get("name").isString().stringValue());
            id = (int) test.get("id").isNumber().getValue();
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
    
    protected class TestPanel extends Composite {
        protected int numColumns;
        protected FlexTable table = new FlexTable();
        protected List testBoxes = new ArrayList(); // List<TestCheckBox>
        String testType = null;
        
        public TestPanel(String testType, int columns) {
            this.testType = testType; 
            numColumns = columns;
            initWidget(table);
        }
        
        public void addTest(TestCheckBox checkBox) {
            if (!checkBox.getTestType().equals(testType))
                throw new RuntimeException(
                    "Inconsistent test type for test " + checkBox.getText());
            int row = testBoxes.size() / numColumns;
            int col = testBoxes.size() % numColumns;
            table.setWidget(row, col, checkBox);
            testBoxes.add(checkBox);
        }
        
        public List getChecked() {
            List result = new ArrayList();
            for(Iterator i = testBoxes.iterator(); i.hasNext(); ) {
                TestCheckBox test = (TestCheckBox) i.next();
                if (test.isChecked())
                    result.add(test);
            }
            return result;
        }
        
        public void setEnabled(boolean enabled) {
            String synchType = null;
            List checked = getChecked();
            if (!checked.isEmpty())
                synchType = ((TestCheckBox) checked.get(0)).getSynchType();
            
            for(Iterator i = testBoxes.iterator(); i.hasNext(); ) {
                TestCheckBox thisBox = (TestCheckBox) i.next();
                boolean boxEnabled = enabled;
                if (enabled && synchType != null)
                    boxEnabled = thisBox.getSynchType().equals(synchType);
                thisBox.setEnabled(boxEnabled);
            }
        }
        
        public void reset() {
            for(Iterator i = testBoxes.iterator(); i.hasNext(); ) {
                ((TestCheckBox) i.next()).setChecked(false);
            }
        }

        public String getTestType() {
            return testType;
        }
    }
    
    protected class ControlTypeSelect extends Composite {
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
    protected TestPanel clientTestsPanel = new TestPanel(CLIENT_TYPE, TEST_COLUMNS), 
                        serverTestsPanel = new TestPanel(SERVER_TYPE, TEST_COLUMNS);
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

    public String getElementId() {
        return "create_job";
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
        StaticDataRepository staticData = StaticDataRepository.getRepository();
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
    
    protected JSONObject getControlFileParams(boolean readyForSubmit) {
        JSONObject params = new JSONObject();
        JSONArray tests = new JSONArray();
        List checkedTests = serverTestsPanel.getChecked();
        if (checkedTests.isEmpty()) {
            checkedTests = clientTestsPanel.getChecked();
        }
        String kernelString = kernel.getText();
        if (!kernelString.equals("")) {
            params.put("kernel", new JSONString(kernelString));
        }
        
        for (int i = 0; i < checkedTests.size(); i++) {
            TestCheckBox test = (TestCheckBox) checkedTests.get(i);
            tests.set(i, new JSONNumber(test.getId()));
        }
        params.put("tests", tests);
        return params;
    }
    
    protected void generateControlFile(final boolean readyForSubmit, 
                                       final SimpleCallback finishedCallback,
                                       final SimpleCallback errorCallback) {
        JSONObject params = getControlFileParams(readyForSubmit);
        rpcProxy.rpcCall("generate_control_file", params, new JsonRpcCallback() {
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
            serverTestsPanel.setEnabled(false);
        }
        else if (!serverTestsPanel.getChecked().isEmpty()) {
            clientTestsPanel.setEnabled(false);
            serverTestsPanel.setEnabled(true);
        }
        else {
            clientTestsPanel.setEnabled(true);
            serverTestsPanel.setEnabled(true);
        }

        kernel.setEnabled(true);
    }
    
    protected void disableInputs() {
        clientTestsPanel.setEnabled(false);
        serverTestsPanel.setEnabled(false);
        kernel.setEnabled(false);
    }
    
    public void initialize() {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
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
                            controlFile.setReadOnly(false);
                            editControlButton.setText(UNEDIT_CONTROL_STRING);
                            controlFilePanel.setOpen(true);
                            controlTypeSelect.setEnabled(true);
                            runSynchronous.setEnabled(true);
                            editControlButton.setEnabled(true);
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
        RootPanel.get("create_priority").add(priorityList);
        RootPanel.get("create_client_tests").add(clientTestsPanel);
        RootPanel.get("create_server_tests").add(serverTestsPanel);
        RootPanel.get("create_edit_control").add(controlFilePanel);
        RootPanel.get("create_submit").add(submitJobButton);
    }
    
    public void reset() {
        jobName.setText("");
        resetPriorityToDefault();
        kernel.setText("");
        clientTestsPanel.reset();
        serverTestsPanel.reset();
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
                
                HostSelector.HostSelection hosts = hostSelector.getSelectedHosts();
                args.put("hosts", Utils.stringsToJSON(hosts.hosts));
                args.put("meta_hosts", Utils.stringsToJSON(hosts.metaHosts));
                
                boolean success =
                    rpcProxy.rpcCall("create_job", args, new JsonRpcCallback() {
                    public void onSuccess(JSONValue result) {
                        int id = (int) result.isNumber().getValue();
                        NotifyManager.getInstance().showMessage(
                                    "Job " + Integer.toString(id) + " created");
                        reset();
                        if (listener != null)
                            listener.onJobCreated(id);
                        submitJobButton.setEnabled(true);
                    }

                    public void onError(JSONObject errorObject) {
                        super.onError(errorObject);
                        submitJobButton.setEnabled(true);
                    }
                });
                
                if (!success)
                    submitJobButton.setEnabled(true);
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
    
    public void refresh() {
        super.refresh();
        hostSelector.refresh();
    }
}
