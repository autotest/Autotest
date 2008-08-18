package autotest.afe;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.LinkSetFilter;
import autotest.common.table.ListFilter;
import autotest.common.table.TableDecorator;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.Paginator;
import autotest.common.ui.TabView;
import autotest.common.ui.TableActionsPanel;
import autotest.common.ui.TableActionsPanel.TableActionsListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Hyperlink;
import com.google.gwt.user.client.ui.RootPanel;

import java.util.Map;
import java.util.Set;


public class JobListView extends TabView implements TableActionsListener {
    protected static final String ALL_USERS = "All Users";
    protected static final String SELECTED_LINK_STYLE = "selected-link";
    protected static final int JOBS_PER_PAGE = 30;
    protected static final int QUEUED = 0, RUNNING = 1, FINISHED = 2, 
                               ALL = 3, LINK_COUNT = 4;
    private static final int DEFAULT_LINK = ALL;
    private static final String[] historyTokens = {"queued", "running", 
                                                     "finished", "all"};
    private static final String[] linkLabels = {"Queued Jobs", "Running Jobs",
                                                  "Finished Jobs", "All Jobs"};
    private static final String[] filterStrings = {"not_yet_run", "running",
                                                     "finished"};
    
    private TableActionsPanel actionPanel = new TableActionsPanel(this, true);
    
    private static final JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected JSONObject jobFilterArgs = new JSONObject();
    protected JobSelectListener selectListener;

    protected JobTable jobTable;
    protected TableDecorator tableDecorator;
    protected JobStateFilter jobStateFilter;
    protected ListFilter ownerFilter;
    protected Paginator paginator;
    protected Hyperlink nextLink, prevLink;
    
    interface JobSelectListener {
        public void onJobSelected(int jobId);
    }
    
    static class JobStateFilter extends LinkSetFilter {
        @Override
        public void addParams(JSONObject params) {
            params.put(filterStrings[getSelectedLink()], 
                       JSONBoolean.getInstance(true));
        }

        @Override
        public boolean isActive() {
            return getSelectedLink() < ALL;
        }
    }
    
    public void abortSelectedJobs() {
        Set<JSONObject> selectedSet = 
            jobTable.getSelectionManager().getSelectedObjects();
        if (selectedSet.isEmpty()) {
            NotifyManager.getInstance().showError("No jobs selected");
            return;
        }
        
        JSONArray ids = new JSONArray();
        for(JSONObject jsonObj : selectedSet) {
            ids.set(ids.size(), jsonObj.get("id").isNumber());
        }
        
        JSONObject params = new JSONObject();
        params.put("job_ids", ids);
        rpcProxy.rpcCall("abort_jobs", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
               refresh();
            }
        });
    }
    
    @Override
    public String getElementId() {
        return "job_list";
    }

    @Override
    public void refresh() {
        super.refresh();
        jobTable.refresh();
    }

    protected void populateUsers() {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray userArray = staticData.getData("users").isArray();
        String[] userStrings = Utils.JSONObjectsToStrings(userArray, "login");
        ownerFilter.setChoices(userStrings);
        String currentUser = staticData.getData("user_login").isString().stringValue();
        ownerFilter.setSelectedChoice(currentUser);
    }

    public JobListView(JobSelectListener listener) {
        selectListener = listener;
    }
    
    @Override
    public void initialize() {
        jobTable = new JobTable();
        jobTable.setRowsPerPage(JOBS_PER_PAGE);
        jobTable.setClickable(true);
        jobTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                int jobId = (int) row.get("id").isNumber().doubleValue();
                selectListener.onJobSelected(jobId);
            }
            
            public void onTableRefreshed() {
                jobTable.getSelectionManager().refreshSelection();
            }
        });
        
        
        RootPanel.get("job_table_actions").add(actionPanel);
        
        tableDecorator = new TableDecorator(jobTable);
        tableDecorator.addPaginators();
        RootPanel.get("job_table").add(tableDecorator);
        
        ownerFilter = new ListFilter("owner");
        ownerFilter.setMatchAllText("All users");
        jobTable.addFilter(ownerFilter);
        populateUsers();
        RootPanel.get("user_list").add(ownerFilter.getWidget());
        
        jobStateFilter = new JobStateFilter();
        for (int i = 0; i < LINK_COUNT; i++)
            jobStateFilter.addLink(linkLabels[i]);
        // all jobs is selected by default
        jobStateFilter.setSelectedLink(DEFAULT_LINK);
        jobStateFilter.addListener(new SimpleCallback() {
            public void doCallback(Object source) {
                updateHistory();
            } 
        });
        jobTable.addFilter(jobStateFilter);
        HorizontalPanel jobControls = new HorizontalPanel();
        jobControls.add(jobStateFilter.getWidget());
        
        RootPanel.get("job_control_links").add(jobControls);
    }

    @Override
    public Map<String, String> getHistoryArguments() {
        Map<String, String> arguments = super.getHistoryArguments();
        arguments.put("state_filter", historyTokens[jobStateFilter.getSelectedLink()]);
        return arguments;
    }
    
    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        String stateFilter = arguments.get("state_filter");
        if (stateFilter == null) {
            jobStateFilter.setSelectedLink(DEFAULT_LINK);
            return;
        }
        
        for (int i = 0; i < LINK_COUNT; i++) {
            if (stateFilter.equals(historyTokens[i])) {
                jobStateFilter.setSelectedLink(i);
                return;
            }
        }
    }

    public ContextMenu getActionMenu() {
        ContextMenu menu = new ContextMenu();
        menu.addItem("Abort jobs", new Command() {
            public void execute() {
                abortSelectedJobs();
            }
        });
        return menu;
    }

    public void onSelectAll(boolean visibleOnly) {
        if (visibleOnly) {
            jobTable.getSelectionManager().selectVisible();
        } else {
            jobTable.getSelectionManager().selectAll();
        }
        jobTable.refreshWidgets();
    }
    
    public void onSelectNone() {
        jobTable.getSelectionManager().deselectAll();
        jobTable.refreshWidgets();
    }
}
