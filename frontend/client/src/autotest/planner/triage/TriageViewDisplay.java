package autotest.planner.triage;

import autotest.common.ui.NotifyManager;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.logical.shared.ResizeEvent;
import com.google.gwt.event.logical.shared.ResizeHandler;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.ScrollPanel;
import com.google.gwt.user.client.ui.VerticalPanel;


public class TriageViewDisplay implements TriageViewPresenter.Display, ResizeHandler {
    
    private static final int HEIGHT_FUDGE = 300;
    
    private VerticalPanel container = new VerticalPanel();
    private ScrollPanel scroll = new ScrollPanel(container);
    private Button triage = new Button("Triage");
    
    public void initialize(HTMLPanel htmlPanel) {
        container.setSpacing(25);
        container.setWidth("90%");
        
        scroll.setSize("100%", getHeightParam(Window.getClientHeight()));
        scroll.setVisible(false);
        triage.setVisible(false);
        
        htmlPanel.add(scroll, "triage_failure_tables");
        htmlPanel.add(triage, "triage_button");
        
        Window.addResizeHandler(this);
    }
    
    @Override
    public void setLoading(boolean loading) {
        NotifyManager.getInstance().setLoading(loading);
        scroll.setVisible(!loading);
        
        scroll.setVisible(true);
        triage.setVisible(true);
    }
    
    @Override
    public FailureTable.Display generateFailureTable(String group, String[] columnNames) {
        FailureTableDisplay display = new FailureTableDisplay(group, columnNames);
        container.add(display);
        return display;
    }
    
    @Override
    public TriagePopup.Display generateTriagePopupDisplay() {
        return new TriagePopupDisplay();
    }

    @Override
    public void clearAllFailureTables() {
        container.clear();
    }

    @Override
    public HasClickHandlers getTriageButton() {
        return triage;
    }

    @Override
    public void onResize(ResizeEvent event) {
        scroll.setHeight(getHeightParam(event.getHeight()));
    }
    
    private String getHeightParam(int height) {
        return (height - HEIGHT_FUDGE) + "px";
    }
}
