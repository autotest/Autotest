package autotest.afe;

import autotest.afe.CreateJobView.JobCreateListener;
import autotest.afe.HostDetailView.HostDetailListener;
import autotest.afe.HostListView.HostListListener;
import autotest.afe.JobDetailView.JobDetailListener;
import autotest.afe.JobListView.JobSelectListener;
import autotest.afe.UserPreferencesView.UserPreferencesListener;
import autotest.common.CustomHistory;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.ui.CustomTabPanel;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.RootPanel;


public class AfeClient implements EntryPoint {
    private JobListView jobList;
    private JobDetailView jobDetail;
    private CreateJobView createJob;
    private HostListView hostListView;
    private HostDetailView hostDetailView;
    private UserPreferencesView userPreferencesView;

    public CustomTabPanel mainTabPanel = new CustomTabPanel();

    /**
     * Application entry point.
     */
    public void onModuleLoad() {
        JsonRpcProxy.setDefaultBaseUrl(JsonRpcProxy.AFE_BASE_URL);
        NotifyManager.getInstance().initialize();
        
        // initialize static data, and don't show main UI until that's done
        StaticDataRepository.getRepository().refresh(
                                 new StaticDataRepository.FinishedCallback() {
            public void onFinished() {
                finishLoading();
            }
        });
    }
    
    protected void finishLoading() {
        String motd = StaticDataRepository.getRepository().getData(
                                               "motd").isString().stringValue();
        RootPanel.get("motd").getElement().setInnerHTML(motd);

        jobList = new JobListView(new JobSelectListener() {
            public void onJobSelected(int jobId) {
                showJob(jobId);
            }
        });
        jobDetail = new JobDetailView(new JobDetailListener() {
            public void onHostSelected(String hostname) {
                showHost(hostname);
            }
            
            public void onCloneJob(JSONValue cloneInfo) {
                createJob.ensureInitialized();
                createJob.cloneJob(cloneInfo);
                mainTabPanel.selectTabView(createJob);
            }
        });
        createJob = AfeUtils.factory.getCreateJobView(new JobCreateListener() {
            public void onJobCreated(int jobId) {
                showJob(jobId);
            }
        });
        hostListView = new HostListView(new HostListListener() {
            public void onHostSelected(String hostname) {
                showHost(hostname);
            }
        });
        hostDetailView = new HostDetailView(new HostDetailListener() {
            public void onJobSelected(int jobId) {
                showJob(jobId);
            }
        });
        userPreferencesView = new UserPreferencesView(new UserPreferencesListener() {
            public void onPreferencesChanged() {
                createJob.onPreferencesChanged();
            }
        });
        
        TabView[] tabViews = new TabView[] {jobList, jobDetail, createJob, 
                                            hostListView, hostDetailView, userPreferencesView};
        for(int i = 0; i < tabViews.length; i++) {
            mainTabPanel.addTabView(tabViews[i]);
        }
        
        final RootPanel tabsRoot = RootPanel.get("tabs");
        tabsRoot.add(mainTabPanel);
        CustomHistory.processInitialToken();
        mainTabPanel.initialize();
        tabsRoot.setStyleName("");
    }
    
    protected void showJob(int jobId) {
        jobDetail.ensureInitialized();
        jobDetail.updateObjectId(Integer.toString(jobId));
        mainTabPanel.selectTabView(jobDetail);
    }

    protected void showHost(String hostname) {
        hostDetailView.ensureInitialized();
        hostDetailView.updateObjectId(hostname);
        mainTabPanel.selectTabView(hostDetailView);
    }
}
