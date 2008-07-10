package autotest.afe;

import autotest.common.Utils;
import autotest.common.table.DataSource;
import autotest.common.table.DynamicTable;
import autotest.common.table.RpcDataSource;
import autotest.common.table.SimpleFilter;
import autotest.common.table.TableDecorator;
import autotest.common.table.DataSource.DataCallback;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.DetailView;
import autotest.common.ui.NotifyManager;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.RootPanel;

public class HostDetailView extends DetailView implements DataCallback {
    private static final String[][] HOST_JOBS_COLUMNS = {
            {"job_id", "Job ID"}, {"job_owner", "Job Owner"}, 
            {"job_name", "Job Name"}, {"status", "Status"}
    };
    public static final int JOBS_PER_PAGE = 20;
    
    public interface HostDetailListener {
        public void onJobSelected(int jobId);
    }
    
    static class HostJobsTable extends DynamicTable {
        public HostJobsTable(String[][] columns, DataSource dataSource) {
            super(columns, dataSource);
        }

        @Override
        protected void preprocessRow(JSONObject row) {
            JSONObject job = row.get("job").isObject();
            int jobId = (int) job.get("id").isNumber().doubleValue();
            row.put("job_id", new JSONString(Integer.toString(jobId)));
            row.put("job_owner", job.get("owner"));
            row.put("job_name", job.get("name"));
        }
    }
    
    protected String hostname = "";
    protected DataSource hostDataSource = new HostDataSource();
    protected DynamicTable jobsTable = 
        new HostJobsTable(HOST_JOBS_COLUMNS, 
                          new RpcDataSource("get_host_queue_entries", 
                                            "get_num_host_queue_entries"));
    protected TableDecorator tableDecorator = new TableDecorator(jobsTable);
    protected SimpleFilter hostFilter = new SimpleFilter();
    protected HostDetailListener listener = null;

    public HostDetailView(HostDetailListener listener) {
        this.listener = listener;
    }

    @Override
    public String getElementId() {
        return "view_host";
    }

    @Override
    protected String getFetchControlsElementId() {
        return "view_host_fetch_controls";
    }
    
    @Override
    protected String getDataElementId() {
        return "view_host_data";
    }
    
    @Override
    protected String getTitleElementId() {
        return "view_host_title";
    }

    @Override
    protected String getNoObjectText() {
        return "No host selected";
    }
    
    @Override
    protected String getObjectId() {
        return hostname;
    }
    
    @Override
    protected void setObjectId(String id) {
        if (id.length() == 0)
            throw new IllegalArgumentException();
        this.hostname = id;
    }
    
    @Override
    protected void fetchData() {
        JSONObject params = new JSONObject();
        params.put("hostname", new JSONString(hostname));
        hostDataSource.updateData(params, this);
    }
    
    public void onGotData(int totalCount) {
        hostDataSource.getPage(null, null, null, null, this);
    }
    
    public void handlePage(JSONArray data) {
        JSONObject hostObject;
        try {
            hostObject = Utils.getSingleValueFromArray(data).isObject();
        }
        catch (IllegalArgumentException exc) {
            NotifyManager.getInstance().showError("No such host found");
            resetPage();
            return;
        }
        
        showField(hostObject, "status", "view_host_status");
        showField(hostObject, "platform", "view_host_platform");
        showField(hostObject, HostDataSource.OTHER_LABELS, "view_host_labels");
        showField(hostObject, HostDataSource.LOCKED_TEXT, "view_host_locked");
        String pageTitle = "Host " + hostname;
        displayObjectData(pageTitle);
        
        hostFilter.setParameter("host__hostname", new JSONString(hostname));
        jobsTable.refresh();
    }

    @Override
    public void initialize() {
        super.initialize();
        
        jobsTable.setRowsPerPage(JOBS_PER_PAGE);
        jobsTable.sortOnColumn("Job ID", DataSource.DESCENDING);
        jobsTable.addFilter(hostFilter);
        jobsTable.setClickable(true);
        jobsTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                JSONObject job = row.get("job").isObject();
                int jobId = (int) job.get("id").isNumber().doubleValue();
                listener.onJobSelected(jobId);
            }

            public void onTableRefreshed() {}
        });
        tableDecorator.addPaginators();
        RootPanel.get("view_host_jobs_table").add(tableDecorator);
    }
}
