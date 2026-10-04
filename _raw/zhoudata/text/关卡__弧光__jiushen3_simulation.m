function threshold_simulation(B1_initial, B2_initial)
    % 设置默认初始值
    if nargin < 2
        B1_initial = 0;
        B2_initial = 0;
    end
    
    % 常量定义
    frame_rate = 30; % 帧率（帧/秒）
    total_time = 30; % 总模拟时间（秒）
    total_frames = total_time * frame_rate; % 总帧数
    burst_duration_frames = round((6 + 2/3) * frame_rate); % 爆条持续时间（帧）
    
    % 初始化对象结构
    units = struct();
    units(1).name = 'A1';
    units(1).X = 0;
    units(1).burst = false;
    units(1).burst_remaining = 0;
    
    units(2).name = 'A2';
    units(2).X = 0;
    units(2).burst = false;
    units(2).burst_remaining = 0;
    
    units(3).name = 'B1';
    units(3).X = B1_initial;
    units(3).burst = false;
    units(3).burst_remaining = 0;
    
    units(4).name = 'B2';
    units(4).X = B2_initial;
    units(4).burst = false;
    units(4).burst_remaining = 0;
    
    % 初始化记录数组
    time_array = (0:total_frames-1) / frame_rate;
    X_history = zeros(4, total_frames);
    burst_history = false(4, total_frames);
    
    % 平A参数
    first_attack_frame = 7;
    attack_interval_frames = round((2 + 4/30) * frame_rate);
    
    % 全局增加参数
    first_global_frame = 10;
    global_interval_frames = 1 * frame_rate;
    
    % 主循环
    for frame = 1:total_frames
        % 更新爆条状态
        for i = 1:4
            if units(i).burst
                units(i).burst_remaining = units(i).burst_remaining - 1;
                if units(i).burst_remaining <= 0
                    units(i).burst = false;
                    units(i).X = 0;
                else
                    units(i).X = 0; % 爆条期间强制X为0
                end
            end
        end
        
        % 执行平A
        if frame >= first_attack_frame && mod(frame - first_attack_frame, attack_interval_frames) == 0
            % 选择目标（按优先级）
            target = [];
            for i = 1:4
                if ~units(i).burst
                    target = units(i);
                    target_idx = i;
                    break;
                end
            end
            
            if ~isempty(target)
                % 对目标增加X值
                if ~target.burst
                    units(target_idx).X = units(target_idx).X + 405.46;
                    
                    % 处理关联增加
                    if target_idx == 1 % A1
                        if ~units(2).burst
                            units(2).X = units(2).X + 282.59;
                        end
                    elseif target_idx == 3 % B1
                        if ~units(4).burst
                            units(4).X = units(4).X + 282.59;
                        end
                    end
                end
            end
        end
        
        % 执行全局增加
        if frame >= first_global_frame && mod(frame - first_global_frame, global_interval_frames) == 0
            for i = 1:4
                if ~units(i).burst
                    units(i).X = units(i).X + 122.86;
                end
            end
        end
        
        % 检查是否触发爆条
        for i = 1:4
            if units(i).X >= 1000 && ~units(i).burst
                units(i).burst = true;
                units(i).burst_remaining = burst_duration_frames;
                units(i).X = 0;
            end
        end
        
        % 记录当前状态
        for i = 1:4
            X_history(i, frame) = units(i).X;
            burst_history(i, frame) = units(i).burst;
        end
    end
    
    % 绘制结果
    figure('Position', [100, 100, 1200, 800]);
    
    % X值随时间变化
    subplot(2, 1, 1);
    hold on;
    colors = ['r', 'g', 'b', 'm'];
    for i = 1:4
        plot(time_array, X_history(i, :), colors(i), 'DisplayName', units(i).name);
    end
    xlabel('时间 (秒)');
    ylabel('元素值');
    title('单位元素值随时间变化');
    legend;
    grid on;
    
    % 爆条状态随时间变化
    subplot(2, 1, 2);
    hold on;
    for i = 1:4
        % 将爆条状态转换为数值以便绘图
        burst_numeric = burst_history(i, :) * (i * 0.2 + 0.8);
        plot(time_array, burst_numeric, colors(i), 'DisplayName', units(i).name);
    end
    xlabel('时间 (秒)');
    ylabel('爆条状态 (偏移显示)');
    title('单位爆条状态随时间变化');
    legend;
    yticks(0.8:0.2:1.6);
    yticklabels({'否', 'A1', 'A2', 'B1', 'B2'});
    grid on;
    
    hold off;
end